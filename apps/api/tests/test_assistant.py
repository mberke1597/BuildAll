"""
Tests for the Chat V2 Assistant endpoints.
Covers: streaming, sessions, feedback, analytics, admin config, rate limiting.
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

os.environ["SKIP_STARTUP"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.core.deps import get_current_user, require_roles  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models import (  # noqa: E402
    Role, User, Company, ChatSession, AssistantMessage,
    ChatFeedback, AIUsage, CompanyAIConfig,
)


# --------------- Fake DB & User fixtures ---------------

class FakeQuery:
    """Chainable mock that always returns empty results."""

    def __init__(self, results=None):
        self._results = results or []

    def filter(self, *a, **kw):
        return self

    def join(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def all(self):
        return self._results

    def first(self):
        return self._results[0] if self._results else None

    def scalar(self):
        return len(self._results)

    def subquery(self):
        return self

    def select_from(self, *a, **kw):
        return self

    @property
    def c(self):
        return type("C", (), {"id": None})()


class FakeDB:
    """Minimal session mock."""

    def __init__(self):
        self._store = {}

    def query(self, *models):
        return FakeQuery()

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def execute(self, *a, **kw):
        return MagicMock(fetchall=lambda: [])


def make_user(role=Role.ADMIN, company_id=1, user_id=1):
    u = User.__new__(User)
    u.id = user_id
    u.company_id = company_id
    u.email = "test@example.com"
    u.role = role
    u.password_hash = "x"
    u.created_at = datetime.utcnow()
    return u


fake_db = FakeDB()
admin_user = make_user(Role.ADMIN)
consultant_user = make_user(Role.CONSULTANT)
client_user = make_user(Role.CLIENT)


def override_db():
    yield fake_db


def override_admin():
    return admin_user


def override_consultant():
    return consultant_user


def override_client():
    return client_user


# Apply overrides
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_current_user] = override_admin

client = TestClient(app)


# --------------- Backward-compatible endpoint ---------------

class TestLegacyAssistant:

    def test_legacy_no_api_key(self):
        """When no AI key is configured, returns a helpful message."""
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            res = client.post("/chat/assistant", json={"message": "hello"})
            assert res.status_code == 200
            assert "not available" in res.json()["answer"].lower() or "configure" in res.json()["answer"].lower()

    @patch("app.routes.assistant.get_ai_provider")
    @patch("app.routes.assistant._check_ai_configured", return_value=True)
    def test_legacy_success(self, mock_cfg, mock_provider):
        mock_ai = MagicMock()
        mock_ai.chat.return_value = "Here is my answer about construction."
        mock_provider.return_value = mock_ai

        res = client.post("/chat/assistant", json={"message": "What is rebar?"})
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] == "Here is my answer about construction."

    @patch("app.routes.assistant._check_rate_limit", side_effect=__import__("fastapi").HTTPException(status_code=429, detail="Rate limit exceeded"))
    @patch("app.routes.assistant._check_ai_configured", return_value=True)
    def test_legacy_rate_limited(self, mock_cfg, mock_rl):
        res = client.post("/chat/assistant", json={"message": "test"})
        assert res.status_code == 429


# --------------- Streaming SSE Endpoint ---------------

class TestStreamingEndpoint:

    @patch("app.routes.assistant.get_ai_provider")
    @patch("app.routes.assistant._check_ai_configured", return_value=True)
    @patch("app.routes.assistant._get_or_create_session")
    @patch("app.routes.assistant._load_history", return_value=[])
    @patch("app.routes.assistant._rag_context", return_value=("", []))
    def test_stream_returns_sse(self, mock_rag, mock_hist, mock_sess, mock_cfg, mock_provider):
        session = ChatSession.__new__(ChatSession)
        session.id = uuid4()
        session.user_id = admin_user.id
        session.project_id = None
        session.summary = None
        mock_sess.return_value = session

        mock_ai = MagicMock()
        mock_ai.chat_stream.return_value = iter(["Hello", " World"])
        mock_provider.return_value = mock_ai

        res = client.post(
            "/chat/assistant/stream",
            json={"message": "Hi there"},
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")

        events = []
        for line in res.text.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        types = [e["type"] for e in events]
        assert "start" in types
        assert "token" in types
        assert "done" in types

        # Verify tokens come through
        token_deltas = [e["delta"] for e in events if e["type"] == "token"]
        assert "".join(token_deltas) == "Hello World"

    def test_stream_no_api_key(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            res = client.post("/chat/assistant/stream", json={"message": "test"})
            assert res.status_code == 200
            events = []
            for line in res.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
            assert any(e.get("type") == "error" for e in events)

    @patch("app.routes.assistant._check_ai_configured", return_value=True)
    @patch("app.routes.assistant._check_rate_limit", side_effect=__import__("fastapi").HTTPException(status_code=429, detail="Rate limit exceeded. Max 60 messages per hour."))
    def test_stream_rate_limited(self, mock_rl, mock_cfg):
        res = client.post("/chat/assistant/stream", json={"message": "test"})
        assert res.status_code == 200  # SSE still returns 200 but with error event
        events = []
        for line in res.text.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        assert any(e.get("type") == "error" for e in events)
        error_msgs = [e.get("message", "") for e in events if e.get("type") == "error"]
        assert any("rate limit" in m.lower() for m in error_msgs)


# --------------- Session Management ---------------

class TestSessions:

    def test_list_sessions_empty(self):
        res = client.get("/chat/sessions")
        assert res.status_code == 200
        assert res.json() == []

    def test_create_session(self):
        # Override query to simulate successful creation
        with patch.object(FakeDB, "query") as mock_q:
            mock_q.return_value = FakeQuery()
            with patch.object(FakeDB, "refresh") as mock_ref:
                def _refresh(obj):
                    pass
                mock_ref.side_effect = _refresh
                res = client.post("/chat/sessions")
                assert res.status_code == 200
                body = res.json()
                assert "id" in body

    def test_get_session_not_found(self):
        res = client.get(f"/chat/sessions/{uuid4()}")
        assert res.status_code == 404

    def test_export_session_not_found(self):
        res = client.get(f"/chat/sessions/{uuid4()}/export")
        assert res.status_code == 404


# --------------- Feedback ---------------

class TestFeedback:

    def test_feedback_message_not_found(self):
        res = client.post("/chat/feedback", json={
            "message_id": str(uuid4()), "rating": 1,
        })
        assert res.status_code == 404

    def test_feedback_invalid_rating(self):
        msg = AssistantMessage.__new__(AssistantMessage)
        msg.id = uuid4()
        msg.session_id = uuid4()
        msg.role = "assistant"
        msg.content = "Hello"
        msg.citations = None
        msg.attachments = None
        msg.token_count = None
        msg.created_at = datetime.utcnow()

        with patch.object(FakeDB, "query") as mock_q:
            mock_q.return_value = FakeQuery([msg])
            res = client.post("/chat/feedback", json={
                "message_id": str(msg.id), "rating": 5,
            })
            assert res.status_code == 400
            assert "rating" in res.json()["detail"].lower()


# --------------- Analytics ---------------

class TestAnalytics:

    def test_analytics_returns_structure(self):
        with patch.object(FakeDB, "query") as mock_q:
            # Return FakeQuery that gives zeros for all aggregations
            fq = FakeQuery()
            # Override scalar to return 0
            fq.scalar = lambda: 0
            # Override first to return a tuple for usage aggregation
            fq.first = lambda: (0, 0, 0, 0.0, 0)
            mock_q.return_value = fq

            res = client.get("/chat/analytics")
            assert res.status_code == 200
            body = res.json()
            assert "total_sessions" in body
            assert "total_messages" in body
            assert "usage" in body


# --------------- Admin AI Config ---------------

class TestAIConfig:

    def test_get_config_returns_default(self):
        """When no config in DB, returns default system prompt."""
        app.dependency_overrides[get_current_user] = override_admin
        res = client.get("/chat/config")
        assert res.status_code == 200

    def test_get_config_forbidden_for_client(self):
        """Clients cannot access config."""
        app.dependency_overrides[get_current_user] = override_client
        res = client.get("/chat/config")
        assert res.status_code == 403
        # Reset
        app.dependency_overrides[get_current_user] = override_admin

    def test_put_config_forbidden_for_consultant(self):
        """Consultants cannot update config (only admins)."""
        app.dependency_overrides[get_current_user] = override_consultant
        res = client.put("/chat/config", json={
            "system_prompt": "You are a test bot.",
            "temperature": 0.5,
        })
        assert res.status_code == 403
        # Reset
        app.dependency_overrides[get_current_user] = override_admin


# --------------- Helper functions unit tests ---------------

class TestHelpers:

    def test_sse_format(self):
        from app.routes.assistant import sse
        result = sse({"type": "token", "delta": "hi"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[6:].strip())
        assert parsed["type"] == "token"
        assert parsed["delta"] == "hi"

    def test_check_ai_configured_gemini(self):
        from app.routes.assistant import _check_ai_configured
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}):
            assert _check_ai_configured() is True

    def test_check_ai_configured_openai(self):
        from app.routes.assistant import _check_ai_configured
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}):
            assert _check_ai_configured() is True

    def test_check_ai_configured_missing(self):
        from app.routes.assistant import _check_ai_configured
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            assert _check_ai_configured() is False

    def test_get_system_prompt_default(self):
        from app.routes.assistant import _get_system_prompt, DEFAULT_SYSTEM_PROMPT
        user = make_user()
        prompt = _get_system_prompt(fake_db, user)
        assert "BuildAll AI" in prompt

    def test_get_rate_limit_default(self):
        from app.routes.assistant import _get_rate_limit
        user = make_user()
        limit = _get_rate_limit(fake_db, user)
        assert limit == 60

    def test_log_usage_noop_when_none(self):
        from app.routes.assistant import _log_usage
        user = make_user()
        # Should not raise
        _log_usage(fake_db, user, uuid4(), None)

    def test_load_history_empty(self):
        from app.routes.assistant import _load_history
        session = ChatSession.__new__(ChatSession)
        session.id = uuid4()
        session.summary = None
        result = _load_history(fake_db, session)
        assert result == []

    def test_load_history_with_summary(self):
        from app.routes.assistant import _load_history
        session = ChatSession.__new__(ChatSession)
        session.id = uuid4()
        session.summary = "User asked about concrete."
        result = _load_history(fake_db, session)
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert "concrete" in result[0]["content"]

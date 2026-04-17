"""
Chat V2 Assistant — Streaming, Sessions, RAG, Feedback, Rate Limiting, Admin Config.
Keeps the original POST /chat/assistant for backward compat and adds:
  POST /chat/assistant/stream   (SSE)
  GET  /chat/sessions           (list sessions)
  GET  /chat/sessions/{id}      (session detail + messages)
  POST /chat/sessions           (create session)
  POST /chat/feedback           (thumbs up/down)
  GET  /chat/analytics          (feedback + usage stats)
  GET  /chat/config             (company AI config)
  PUT  /chat/config             (update company AI config)
  GET  /chat/sessions/{id}/export (export conversation)
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import (
    AIUsage,
    AssistantMessage,
    ChatFeedback,
    ChatSession,
    CompanyAIConfig,
    Project,
    ProjectMember,
    Role,
    User,
)
from app.schemas import (
    ChatAnalyticsOut,
    ChatRequest,
    ChatResponse,
    Citation,
    CompanyAIConfigIn,
    CompanyAIConfigOut,
    AIUsageOut,
    FeedbackRequest,
    FeedbackResponse,
    SessionDetailOut,
    SessionMessageOut,
    SessionOut,
)
from app.services.ai import get_ai_provider

router = APIRouter(prefix="/chat", tags=["assistant"])

# --------------- Constants / Helpers ---------------

DEFAULT_SYSTEM_PROMPT = """You are BuildAll AI, an expert construction consultant assistant. You help with:
- Construction project management and best practices
- Cost estimation guidance and budgeting tips
- Material selection and quality considerations
- Building codes and safety regulations overview
- Project timeline and scheduling advice
- Team coordination and communication strategies
- Sustainability and green building practices

Always be professional, helpful, and concise. If you don't know something specific,
acknowledge it and provide general guidance. Never make up specific regulations or prices -
suggest consulting local authorities or getting professional quotes instead.

Keep responses clear and actionable. Use markdown formatting: bullet points for lists,
tables for comparisons, **bold** for emphasis, and code blocks where appropriate.

Always respond in the same language as the user's message."""

MAX_HISTORY_MESSAGES = 50
COMPACTION_THRESHOLD = 30


def _check_ai_configured() -> bool:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    elif provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return False


def _get_system_prompt(db: Session, user: User, language: Optional[str] = None) -> str:
    config = (
        db.query(CompanyAIConfig)
        .filter(CompanyAIConfig.company_id == user.company_id)
        .first()
    )
    prompt = DEFAULT_SYSTEM_PROMPT
    if config and config.system_prompt:
        prompt = config.system_prompt
    if config and config.preferred_language:
        prompt += f"\n\nAlways respond in {config.preferred_language}."
    elif language:
        prompt += f"\n\nAlways respond in {language}."
    return prompt


def _get_rate_limit(db: Session, user: User) -> int:
    config = (
        db.query(CompanyAIConfig)
        .filter(CompanyAIConfig.company_id == user.company_id)
        .first()
    )
    if config and config.rate_limit_per_hour:
        return config.rate_limit_per_hour
    return 60


def _check_rate_limit(db: Session, user: User):
    limit = _get_rate_limit(db, user)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = (
        db.query(func.count(AssistantMessage.id))
        .join(ChatSession)
        .filter(
            ChatSession.user_id == user.id,
            AssistantMessage.role == "user",
            AssistantMessage.created_at >= one_hour_ago,
        )
        .scalar()
        or 0
    )
    if count >= limit:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Max {limit} messages per hour.")


def _get_or_create_session(
    db: Session, user: User, session_id: Optional[UUID], project_id: Optional[int]
) -> ChatSession:
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    session = ChatSession(
        id=uuid4(), user_id=user.id, project_id=project_id,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _load_history(db: Session, session: ChatSession) -> List[dict]:
    msgs = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.created_at.asc())
        .all()
    )
    history = []
    if session.summary:
        history.append({"role": "system", "content": f"Previous conversation summary: {session.summary}"})
    recent = msgs[-MAX_HISTORY_MESSAGES:] if len(msgs) > MAX_HISTORY_MESSAGES else msgs
    for m in recent:
        history.append({"role": m.role, "content": m.content})
    return history


def _maybe_compact(db: Session, session: ChatSession, ai_provider):
    msg_count = (
        db.query(func.count(AssistantMessage.id))
        .filter(AssistantMessage.session_id == session.id)
        .scalar() or 0
    )
    if msg_count < COMPACTION_THRESHOLD:
        return
    all_msgs = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.created_at.asc())
        .all()
    )
    if len(all_msgs) <= 10:
        return
    older = all_msgs[:-10]
    text_to_summarize = "\n".join([f"{m.role}: {m.content[:500]}" for m in older])
    try:
        summary = ai_provider.chat(
            "You are a helpful summarizer. Be concise but thorough.",
            "Summarize this conversation preserving facts, decisions, and open questions:\n\n" + text_to_summarize,
        )
        session.summary = summary
        db.commit()
    except Exception:
        pass


def _auto_title(db: Session, session: ChatSession, first_message: str, ai_provider):
    if session.title:
        return
    try:
        title = ai_provider.chat(
            "Generate a short title (max 6 words) for a conversation. Return ONLY the title text, no quotes.",
            first_message,
        )
        session.title = title.strip()[:80]
        db.commit()
    except Exception:
        session.title = first_message[:60]
        db.commit()


def _rag_context(db: Session, user: User, project_id: int, query_text: str, ai_provider):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.company_id == user.company_id)
        .first()
    )
    if not project:
        return "", []
    if user.role == Role.CLIENT:
        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
            .first()
        )
        if not member:
            return "", []
    try:
        query_emb = ai_provider.embed([query_text])[0]
    except Exception:
        return "", []

    embedding_str = "[" + ",".join(str(x) for x in query_emb) + "]"
    sql = text("""
        SELECT dc.id, dc.text, dc.page_number, d.id as document_id, m.filename as document_name
        FROM doc_chunks dc
        JOIN documents d ON d.id = dc.document_id
        JOIN media m ON m.id = d.media_id
        WHERE d.project_id = :project_id
        ORDER BY dc.embedding <-> :embedding::vector
        LIMIT 4
    """)
    rows = db.execute(sql, {"project_id": project_id, "embedding": embedding_str}).fetchall()

    citations = []
    context = "\n\nPROJECT CONTEXT (from uploaded documents):\n"
    for i, r in enumerate(rows, 1):
        snippet = r.text[:300]
        citations.append({
            "ref": i, "document_id": r.document_id, "document_name": r.document_name,
            "chunk_id": r.id, "page_number": r.page_number, "snippet": snippet,
        })
        page_info = f", p.{r.page_number}" if r.page_number else ""
        context += f"[{i}] (doc: {r.document_name}{page_info}) {r.text[:500]}\n\n"
    if citations:
        context += (
            "\nCite sources using reference numbers like [1], [2]. "
            "If the answer is not in the provided documents, say so clearly.\n"
        )
    return context, citations


def _log_usage(db: Session, user: User, session_id: UUID, usage: Optional[dict]):
    if not usage:
        return
    record = AIUsage(
        company_id=user.company_id, user_id=user.id, session_id=session_id,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        estimated_cost_usd=usage.get("total_tokens", 0) * 0.000003,
    )
    db.add(record)
    db.commit()


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# --------------- Backward-compatible non-stream endpoint ---------------


class AssistantRequest(BaseModel):
    message: str


class AssistantResponse(BaseModel):
    answer: str


@router.post("/assistant", response_model=AssistantResponse)
def chat_with_assistant(
    payload: AssistantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Original non-streaming endpoint (backward compat)."""
    if not _check_ai_configured():
        provider_name = os.getenv("AI_PROVIDER", "gemini").upper()
        return AssistantResponse(
            answer=f"AI features are not available. Please configure {provider_name}_API_KEY."
        )
    try:
        _check_rate_limit(db, user)
        system = _get_system_prompt(db, user)
        ai = get_ai_provider()
        answer = ai.chat(system, payload.message)
    except HTTPException:
        raise
    except Exception as e:
        return AssistantResponse(answer=f"AI service is currently unavailable. Error: {str(e)[:150]}")

    log_audit(db, company_id=user.company_id, user_id=user.id, action="AI_CHAT",
              meta={"message_preview": payload.message[:100]})
    return AssistantResponse(answer=answer)


# --------------- SSE Streaming Endpoint ---------------


@router.post("/assistant/stream")
def assistant_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Streaming SSE endpoint. Events: start, token, citations, done, error.
    """
    if not _check_ai_configured():
        provider_name = os.getenv("AI_PROVIDER", "gemini").upper()
        def error_gen():
            yield sse({"type": "error", "message": f"AI not configured. Set {provider_name}_API_KEY."})
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    try:
        _check_rate_limit(db, user)
    except HTTPException as e:
        def rate_error():
            yield sse({"type": "error", "message": e.detail})
        return StreamingResponse(rate_error(), media_type="text/event-stream")

    session = _get_or_create_session(db, user, payload.session_id, payload.project_id)

    user_msg = AssistantMessage(
        id=uuid4(), session_id=session.id, role="user", content=payload.message,
        attachments=([{"media_id": mid} for mid in payload.attachments] if payload.attachments else None),
    )
    db.add(user_msg)
    db.commit()

    history = _load_history(db, session)
    system = _get_system_prompt(db, user)

    citations = []
    project_id = payload.project_id or session.project_id
    if project_id:
        try:
            ai_temp = get_ai_provider()
            rag_context, citations = _rag_context(db, user, project_id, payload.message, ai_temp)
            if rag_context:
                system += rag_context
        except Exception:
            pass

    if not history or history[-1]["content"] != payload.message:
        history.append({"role": "user", "content": payload.message})

    assistant_msg_id = uuid4()

    def generate():
        yield sse({"type": "start", "session_id": str(session.id), "message_id": str(assistant_msg_id)})
        full_response = ""
        try:
            ai = get_ai_provider()
            for delta in ai.chat_stream(system=system, messages=history):
                full_response += delta
                yield sse({"type": "token", "delta": delta})
            if citations:
                yield sse({"type": "citations", "citations": citations})
            yield sse({"type": "done"})
        except Exception as e:
            yield sse({"type": "error", "message": str(e)[:200]})
            full_response = full_response or f"Error: {str(e)[:200]}"

        try:
            asst_msg = AssistantMessage(
                id=assistant_msg_id, session_id=session.id, role="assistant",
                content=full_response, citations=citations if citations else None,
            )
            db.add(asst_msg)
            db.commit()
            msg_count = (
                db.query(func.count(AssistantMessage.id))
                .filter(AssistantMessage.session_id == session.id).scalar() or 0
            )
            if msg_count <= 2:
                try:
                    _auto_title(db, session, payload.message, get_ai_provider())
                except Exception:
                    pass
            try:
                _maybe_compact(db, session, get_ai_provider())
            except Exception:
                pass
        except Exception:
            pass

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# --------------- Session Management ---------------


@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ChatSession).filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc()).limit(50).all()
    )


@router.post("/sessions", response_model=SessionOut)
def create_session(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = ChatSession(
        id=uuid4(), user_id=user.id, project_id=project_id,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = (
        db.query(AssistantMessage).filter(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.created_at.asc()).all()
    )
    return SessionDetailOut(
        session=SessionOut.model_validate(session),
        messages=[SessionMessageOut.model_validate(m) for m in msgs],
    )


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: UUID, format: str = "markdown",
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = (
        db.query(AssistantMessage).filter(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.created_at.asc()).all()
    )
    if format == "json":
        return {
            "session_id": str(session.id), "title": session.title,
            "created_at": session.created_at.isoformat(),
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat(), "citations": m.citations}
                for m in msgs
            ],
        }
    lines = [f"# {session.title or 'Chat Conversation'}\n"]
    lines.append(f"*Exported on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n")
    for m in msgs:
        role_label = "**You**" if m.role == "user" else "**BuildAll AI**"
        lines.append(f"### {role_label} — {m.created_at.strftime('%H:%M')}\n")
        lines.append(m.content + "\n")
        if m.citations:
            lines.append("\n*Sources:*\n")
            for c in m.citations:
                ref = c.get('ref', '?')
                doc = c.get('document_name', 'Unknown')
                page = f" (p.{c['page_number']})" if c.get("page_number") else ""
                lines.append(f"- [{ref}] {doc}{page}\n")
        lines.append("---\n")
    return {"content": "\n".join(lines), "format": "markdown"}


# --------------- Feedback ---------------


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    payload: FeedbackRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    msg = (
        db.query(AssistantMessage).join(ChatSession)
        .filter(AssistantMessage.id == payload.message_id, ChatSession.user_id == user.id).first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be +1 or -1")
    feedback = ChatFeedback(
        message_id=payload.message_id, user_id=user.id, rating=payload.rating, comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    log_audit(db, company_id=user.company_id, user_id=user.id, action="AI_FEEDBACK",
              meta={"message_id": str(payload.message_id), "rating": payload.rating})
    return feedback


# --------------- Analytics ---------------


@router.get("/analytics", response_model=ChatAnalyticsOut)
def chat_analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company_sessions = (
        db.query(ChatSession.id).join(User, ChatSession.user_id == User.id)
        .filter(User.company_id == user.company_id).subquery()
    )
    total_sessions = db.query(func.count()).select_from(company_sessions).scalar() or 0
    total_messages = (
        db.query(func.count(AssistantMessage.id))
        .filter(AssistantMessage.session_id.in_(db.query(company_sessions.c.id))).scalar() or 0
    )
    positive = (
        db.query(func.count(ChatFeedback.id)).join(AssistantMessage)
        .filter(AssistantMessage.session_id.in_(db.query(company_sessions.c.id)), ChatFeedback.rating == 1)
        .scalar() or 0
    )
    negative = (
        db.query(func.count(ChatFeedback.id)).join(AssistantMessage)
        .filter(AssistantMessage.session_id.in_(db.query(company_sessions.c.id)), ChatFeedback.rating == -1)
        .scalar() or 0
    )
    total_fb = positive + negative
    satisfaction_rate = (positive / total_fb * 100) if total_fb > 0 else None
    usage_agg = (
        db.query(
            func.coalesce(func.sum(AIUsage.prompt_tokens), 0),
            func.coalesce(func.sum(AIUsage.completion_tokens), 0),
            func.coalesce(func.sum(AIUsage.total_tokens), 0),
            func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0.0),
            func.count(AIUsage.id),
        ).filter(AIUsage.company_id == user.company_id).first()
    )
    return ChatAnalyticsOut(
        total_sessions=total_sessions, total_messages=total_messages,
        satisfaction_rate=satisfaction_rate, positive_feedback=positive, negative_feedback=negative,
        usage=AIUsageOut(
            total_prompt_tokens=usage_agg[0], total_completion_tokens=usage_agg[1],
            total_tokens=usage_agg[2], estimated_cost_usd=float(usage_agg[3]), request_count=usage_agg[4],
        ),
    )


# --------------- Admin AI Config ---------------


@router.get("/config", response_model=CompanyAIConfigOut)
def get_ai_config(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT))):
    config = db.query(CompanyAIConfig).filter(CompanyAIConfig.company_id == user.company_id).first()
    if not config:
        config = CompanyAIConfig(id=0, company_id=user.company_id, system_prompt=DEFAULT_SYSTEM_PROMPT, temperature=0.2)
    return config


@router.put("/config", response_model=CompanyAIConfigOut)
def update_ai_config(
    payload: CompanyAIConfigIn, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN)),
):
    config = db.query(CompanyAIConfig).filter(CompanyAIConfig.company_id == user.company_id).first()
    if not config:
        config = CompanyAIConfig(company_id=user.company_id)
        db.add(config)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    log_audit(db, company_id=user.company_id, user_id=user.id, action="AI_CONFIG_UPDATE")
    return config

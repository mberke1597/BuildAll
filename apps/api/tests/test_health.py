import os
from fastapi.testclient import TestClient

os.environ["SKIP_STARTUP"] = "true"

from app.main import app  # noqa: E402


def test_health():
    client = TestClient(app)
    res = client.get("/healthz")
    assert res.status_code == 200

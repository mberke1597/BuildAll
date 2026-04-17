#!/bin/sh
set -e

python - <<'PY'
import os
import time
import psycopg2

dsn = os.getenv("DATABASE_URL")
if not dsn:
    raise SystemExit("DATABASE_URL not set")
dsn = dsn.replace("postgresql+psycopg2://", "postgresql://")

for i in range(60):
    try:
        conn = psycopg2.connect(dsn)
        conn.close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("DB not ready after 60s")
PY

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000

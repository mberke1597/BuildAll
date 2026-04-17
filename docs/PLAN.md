# MVP Plan

Milestone 1: Repo skeleton + docs
- Create monorepo layout (/apps, /infra, /docs)
- Draft architecture + API + runbook docs

Milestone 2: Backend + worker foundation
- FastAPI app with auth, RBAC, tenants, core CRUD
- PostgreSQL schema + Alembic migrations + seed data
- RQ worker with document processing + embeddings

Milestone 3: Web app MVP
- Next.js UI for auth, projects, chat, documents, ask, cost estimate, parcel lookup
- WebSocket chat and file/voice handling

Milestone 4: Infra + tests
- Docker compose with postgres+pgvector, redis, minio, api, worker, web
- Pytest + Playwright smoke
- Lint/format config

Milestone 5: Stabilize
- Run tests, fix issues
- Ensure docker compose up --build works locally

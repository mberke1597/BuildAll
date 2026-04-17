# Architecture

## Overview
- Monorepo with `apps/web`, `apps/api`, `apps/worker`, `infra`, `docs`.
- Postgres + pgvector for relational data and embeddings.
- MinIO for private media storage.
- Redis + RQ for background document processing.

## Key flows
1. Auth
   - JWT issued via `/auth/login` and stored in browser localStorage.
2. Chat
   - WebSocket `/ws/projects/{id}?token=...` for realtime text messages.
3. Documents (RAG)
   - Upload to MinIO, create `Document`, enqueue worker.
   - Worker extracts text, chunks, embeds, stores `DocChunk`.
4. Ask
   - Retrieve top-k chunks from project scope and answer with citations.

## Security
- JWT auth
- RBAC (Admin/Consultant/Client)
- Tenant isolation via `company_id`
- Audit logs for login, upload, doc indexing, AI question

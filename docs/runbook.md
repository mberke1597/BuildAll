# Runbook

## Local dev
1. `docker compose up --build`
2. Web: http://localhost:3000
3. API: http://localhost:8000/docs

## Common issues
- Docker not installed: install Docker Desktop.
- MinIO access: use `minioadmin / minioadmin` at http://localhost:9001.
- If docs/embeddings fail, ensure `OPENAI_API_KEY` is set.

## Reset
- `docker compose down -v` to wipe volumes.

# API

Base URL: `http://localhost:8000`

## Auth
- `POST /auth/login`
- `GET /auth/me`

## Projects
- `POST /projects`
- `GET /projects`
- `GET /projects/{id}`
- `PUT /projects/{id}`
- `POST /projects/{id}/members`

## Chat
- `GET /projects/{id}/messages`
- `WS /ws/projects/{id}?token=JWT`

## Media & Docs
- `POST /projects/{id}/upload`
- `POST /projects/{id}/documents/upload`
- `GET /projects/{id}/documents`

## RAG
- `POST /projects/{id}/ask`

## Parcel Lookup
- `POST /projects/{id}/parcel-lookup`

## Cost Estimate
- `POST /projects/{id}/cost/estimate`

## Health
- `GET /healthz`

# BuildAll MVP

Production-quality MVP monorepo for a 24/7 Construction Consultant ↔ Client communication app.

## ✨ Features

- **Modern Dark Theme UI** - Professional, clean interface with smooth animations
- **AI Chatbot Assistant** - 24/7 AI-powered construction consultant (floating chat widget)
- **Real-time Project Chat** - WebSocket-based team communication
- **Document Management** - Upload, process, and search project documents
- **AI Document Q&A** - Ask questions about your uploaded documents with citations
- **Cost Estimation** - AI-powered project cost calculations
- **Analytics Dashboard** - Track project activity and audit logs
- **Multi-role Support** - Admin, Consultant, and Client roles

## Quick start
1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` (required for AI features).
2. Run `docker compose up --build`.
3. Open web: http://localhost:3000
4. API: http://localhost:8000/docs

## Demo script
1. Login as consultant: `consultant@demo.com / Consultant123!`
2. Create a project.
3. Invite a client (add member from API or admin account).
4. Send a text + file + voice note in project chat.
5. Upload a PDF and ask a question with citations.
6. Run a cost estimate.
7. **Try the AI chatbot** - click the chat bubble in the bottom-right corner!

## Demo Accounts
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@demo.com | Admin123! |
| Consultant | consultant@demo.com | Consultant123! |
| Client | client@demo.com | Client123! |

## Services
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Worker health: http://localhost:8001/healthz
- MinIO: http://localhost:9001

## Tests
- Backend: `pytest` (apps/api)
- Frontend: `npm run test:e2e` (apps/web)

## Tech Stack
- **Frontend**: Next.js 14, React 18, TypeScript
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL + pgvector
- **AI**: OpenAI GPT-4 / GPT-3.5, Embeddings
- **Storage**: MinIO (S3-compatible)
- **Queue**: Redis + RQ

## Notes
- Migrations run on API container startup (`alembic upgrade head`).
- The AI chatbot works with or without login (limited features when logged out).

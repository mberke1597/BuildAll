# BuildAll

> AI-powered Construction Project Management Platform — 24/7 Consultant ↔ Client communication with autonomous AI agents.

---

## ✨ Features

### 🤖 AI Agent Layer (ReAct Architecture)
- **Risk Monitor Agent** — Autonomously scans project data, identifies risks, and writes CRITICAL alerts to the database
- **Cost Advisor Agent** — Analyzes project cost data and generates budget recommendations
- **Document Analyst Agent** — Processes uploaded documents and extracts key insights
- All agents use **Think → Act → Observe** reasoning loop (ReAct pattern)

### 💬 Communication & Collaboration
- **AI Chatbot Assistant** — 24/7 AI-powered construction consultant (floating chat widget)
- **Real-time Project Chat** — WebSocket-based team communication
- **Multi-role Support** — Admin, Consultant, and Client roles

### 📁 Document & Data Management
- **Document Management** — Upload, process, and search project documents
- **AI Document Q&A** — Ask questions about uploaded documents with citations
- **Cost Estimation** — AI-powered project cost calculations
- **Analytics Dashboard** — Track project activity and audit logs

---

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/mberke1597/BuildAll.git
cd BuildAll

# 2. Set up environment
cp .env.example .env
# Edit .env and set GEMINI_API_KEY

# 3. Start all services
docker compose up --build

# 4. Open
#   Web:      http://localhost:3000
#   API docs: http://localhost:8000/docs
```

---

## 🔑 Demo Accounts

| Role       | Email                  | Password       |
|------------|------------------------|----------------|
| Admin      | admin@demo.com         | Admin123!      |
| Consultant | consultant@demo.com    | Consultant123! |
| Client     | client@demo.com        | Client123!     |

---

## 🤖 Running AI Agents

```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"consultant@demo.com","password":"Consultant123!"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Run Risk Monitor Agent
curl -s -X POST http://localhost:8000/agents/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_id":1,"agent_type":"risk_monitor"}' | python3 -m json.tool

# Available agent types:
#   risk_monitor      — detects project risks autonomously
#   cost_advisor      — analyzes budget and cost data
#   document_analyst  — extracts insights from documents
```

### Example Agent Output
```json
{
  "run_id": 5,
  "status": "completed",
  "agent_type": "risk_monitor",
  "steps_count": 14,
  "total_elapsed_ms": 10487,
  "answer": {
    "project_health_score": 10,
    "top_3_immediate_concerns": [
      "Complete absence of project schedule data",
      "Complete absence of project cost data",
      "Complete absence of RFI data"
    ],
    "recommended_actions": ["..."]
  }
}
```

---

## 🧠 Agent Architecture

```
User Request
     │
     ▼
 Orchestrator
     │
     ▼
┌─────────────────────────────┐
│        ReAct Loop           │
│                             │
│  1. THINK  — reason about   │
│             current state   │
│  2. ACT    — call a tool    │
│  3. OBSERVE — process result│
│  4. REPEAT until done       │
└─────────────────────────────┘
     │
     ▼
 Tools Available:
  • get_project_schedule
  • get_project_cost_summary
  • get_project_rfis
  • get_project_risks
  • create_risk
  • get_project_documents
```

---

## 🛠 Tech Stack

| Layer      | Technology                                      |
|------------|-------------------------------------------------|
| Frontend   | Next.js 14, React 18, TypeScript                |
| Backend    | FastAPI, SQLAlchemy, PostgreSQL + pgvector      |
| AI         | Gemini 2.5 Flash (chat + agents + embeddings)   |
| Storage    | MinIO (S3-compatible)                           |
| Queue      | Redis + RQ                                      |
| Deploy     | Docker Compose / Railway                        |

---

## 📡 Services

| Service      | URL                          |
|--------------|------------------------------|
| Web          | http://localhost:3000        |
| API          | http://localhost:8000        |
| API Docs     | http://localhost:8000/docs   |
| Worker       | http://localhost:8001/healthz|
| MinIO        | http://localhost:9001        |

---

## 🧪 Tests

```bash
# Backend
cd apps/api && pytest

# Frontend
cd apps/web && npm run test:e2e
```

---

## 📝 Notes

- Migrations run automatically on API startup (`alembic upgrade head`)
- Agents require a valid `GEMINI_API_KEY` in `.env`
- Gemini free tier has rate limits — agents may take 30–120s on first run
- The AI chatbot works with or without login (limited features when logged out)

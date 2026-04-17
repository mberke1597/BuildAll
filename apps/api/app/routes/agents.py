"""
Agent API Endpoints

POST /agents/run         — Run agent synchronously (small tasks)
POST /agents/run/async   — Enqueue agent for background execution
GET  /agents/runs        — List recent runs for a project
GET  /agents/runs/{id}   — Get full run details including step-by-step trace
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.agents.models_extension import AgentRun
from app.agents.orchestrator import AgentType, run_agent
from app.core.audit import log_audit
from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Project, Role, User

router = APIRouter(prefix="/agents", tags=["agents"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    project_id: int
    agent_type: str  # "document_analyst" | "risk_monitor" | "cost_advisor"
    task: Optional[str] = None  # custom task override
    context: Optional[Dict[str, Any]] = {}


class AgentRunOut(BaseModel):
    run_id: int
    status: str
    agent_type: str
    answer: Optional[str] = None
    artifacts: Optional[List[Dict]] = None
    steps_count: int = 0
    total_elapsed_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunDetailOut(AgentRunOut):
    task: str
    context_json: Optional[Dict] = None
    steps: Optional[List[Dict]] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class AsyncRunOut(BaseModel):
    job_id: str
    run_id: int
    status: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _validate_project(db: Session, user: User, project_id: int) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.company_id == user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _default_task(agent_type: str, context: Dict) -> str:
    if agent_type == "document_analyst":
        doc_id = context.get("document_id", "?")
        return f"Analyze document {doc_id} — identify ambiguous clauses and risk factors."
    elif agent_type == "risk_monitor":
        return "Perform a comprehensive project risk scan."
    elif agent_type == "cost_advisor":
        return "Perform a full cost analysis with budget projections."
    return "Run agent analysis."


# ─── POST /agents/run — Synchronous ──────────────────────────────────────────


@router.post("/run", response_model=AgentRunOut)
def run_agent_sync(
    payload: AgentRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    """Run an agent synchronously. Best for quick tasks (<30s)."""
    # Validate
    _validate_project(db, user, payload.project_id)

    try:
        AgentType(payload.agent_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type: '{payload.agent_type}'. "
            f"Valid: {[e.value for e in AgentType]}",
        )

    task = payload.task or _default_task(payload.agent_type, payload.context or {})
    context = {
        "project_id": payload.project_id,
        "user_id": user.id,
        **(payload.context or {}),
    }

    # Create run record
    agent_run = AgentRun(
        project_id=payload.project_id,
        triggered_by=user.id,
        agent_type=payload.agent_type,
        status="running",
        task=task,
        context_json=context,
        created_at=datetime.utcnow(),
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)

    # Execute
    try:
        result = run_agent(task=task, agent_type=payload.agent_type, context=context, db=db)

        agent_run.status = "completed" if result.success else "failed"
        agent_run.answer = result.answer
        agent_run.steps_json = [s.to_dict() for s in result.steps]
        agent_run.artifacts_json = result.artifacts
        agent_run.total_elapsed_ms = result.total_elapsed_ms
        agent_run.error = result.error
        agent_run.completed_at = datetime.utcnow()
        db.commit()

        log_audit(
            db,
            company_id=user.company_id,
            user_id=user.id,
            action="AGENT_RUN",
            meta={
                "run_id": agent_run.id,
                "agent_type": payload.agent_type,
                "artifacts_count": len(result.artifacts),
                "elapsed_ms": result.total_elapsed_ms,
            },
        )

    except Exception as exc:
        agent_run.status = "failed"
        agent_run.error = str(exc)[:500]
        agent_run.completed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}")

    return AgentRunOut(
        run_id=agent_run.id,
        status=agent_run.status,
        agent_type=agent_run.agent_type,
        answer=agent_run.answer,
        artifacts=agent_run.artifacts_json,
        steps_count=len(agent_run.steps_json or []),
        total_elapsed_ms=agent_run.total_elapsed_ms,
        created_at=agent_run.created_at,
    )


# ─── POST /agents/run/async — Background Execution ───────────────────────────


@router.post("/run/async", response_model=AsyncRunOut)
def run_agent_async(
    payload: AgentRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.CONSULTANT)),
):
    """Enqueue an agent for background execution. Returns immediately with job_id."""
    _validate_project(db, user, payload.project_id)

    try:
        AgentType(payload.agent_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type: '{payload.agent_type}'.",
        )

    task = payload.task or _default_task(payload.agent_type, payload.context or {})
    context = {
        "project_id": payload.project_id,
        "user_id": user.id,
        **(payload.context or {}),
    }

    # Create run record with pending status
    agent_run = AgentRun(
        project_id=payload.project_id,
        triggered_by=user.id,
        agent_type=payload.agent_type,
        status="pending",
        task=task,
        context_json=context,
        created_at=datetime.utcnow(),
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)

    # Enqueue background job
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_conn = Redis.from_url(redis_url)
    q = Queue(connection=redis_conn)

    job = q.enqueue(
        "tasks.process_agent_task",
        agent_run.id,
        job_timeout=300,  # 5 minute timeout
    )

    log_audit(
        db,
        company_id=user.company_id,
        user_id=user.id,
        action="AGENT_RUN_ASYNC",
        meta={"run_id": agent_run.id, "agent_type": payload.agent_type, "job_id": job.id},
    )

    return AsyncRunOut(
        job_id=job.id,
        run_id=agent_run.id,
        status="pending",
    )


# ─── GET /agents/runs — List Runs ────────────────────────────────────────────


@router.get("/runs", response_model=List[AgentRunOut])
def list_agent_runs(
    project_id: int = Query(..., description="Filter by project ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the 20 most recent agent runs for a project."""
    _validate_project(db, user, project_id)

    runs = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        AgentRunOut(
            run_id=r.id,
            status=r.status,
            agent_type=r.agent_type,
            answer=r.answer,
            artifacts=r.artifacts_json,
            steps_count=len(r.steps_json or []),
            total_elapsed_ms=r.total_elapsed_ms,
            created_at=r.created_at,
        )
        for r in runs
    ]


# ─── GET /agents/runs/{run_id} — Full Details ────────────────────────────────


@router.get("/runs/{run_id}", response_model=AgentRunDetailOut)
def get_agent_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get full agent run details including the step-by-step reasoning trace."""
    agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()

    if not agent_run:
        raise HTTPException(status_code=404, detail="Agent run not found")

    # Verify access
    _validate_project(db, user, agent_run.project_id)

    return AgentRunDetailOut(
        run_id=agent_run.id,
        status=agent_run.status,
        agent_type=agent_run.agent_type,
        task=agent_run.task,
        context_json=agent_run.context_json,
        answer=agent_run.answer,
        artifacts=agent_run.artifacts_json,
        steps=agent_run.steps_json,
        steps_count=len(agent_run.steps_json or []),
        total_elapsed_ms=agent_run.total_elapsed_ms,
        error=agent_run.error,
        created_at=agent_run.created_at,
        completed_at=agent_run.completed_at,
    )

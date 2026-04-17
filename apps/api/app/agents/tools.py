"""
Agent Tool Library — 8 construction intelligence tools.

Each tool is a function: (db: Session, **kwargs) -> str
Tools create real DB records and return structured observation strings.
"""
from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.agents.base import Tool
from app.models import (
    CostLine,
    DocChunk,
    Document,
    Media,
    Project,
    RFI,
    RfiStatus,
    Risk,
    RiskSeverity,
    RiskStatus,
    ScheduleItem,
)
from app.services.ai import get_ai_provider


# ─── 1. Search Project Documents (pgvector) ──────────────────────────────────


def search_project_documents(
    db: Session,
    project_id: int,
    query: str,
    limit: int = 5,
    **kwargs,
) -> str:
    """Semantic search across project documents using pgvector."""
    try:
        ai = get_ai_provider()
        query_emb = ai.embed([query])[0]
    except Exception as exc:
        return f"[ERROR] Embedding failed: {exc}"

    embedding_str = "[" + ",".join(str(x) for x in query_emb) + "]"

    sql = text("""
        SELECT dc.text, dc.page_number, m.filename, dc.id as chunk_id,
               d.id as document_id
        FROM doc_chunks dc
        JOIN documents d ON d.id = dc.document_id
        JOIN media m ON m.id = d.media_id
        WHERE d.project_id = :pid
          AND d.status = 'READY'
        ORDER BY dc.embedding <-> :emb::vector
        LIMIT :lim
    """)

    rows = db.execute(sql, {"pid": project_id, "emb": embedding_str, "lim": limit}).fetchall()

    if not rows:
        return "No relevant document chunks found for this query."

    results = []
    for i, r in enumerate(rows, 1):
        page = f" (page {r.page_number})" if r.page_number else ""
        snippet = r.text[:400].replace("\n", " ")
        results.append(f"[{i}] {r.filename}{page}:\n{snippet}")

    return f"Found {len(rows)} relevant chunks:\n\n" + "\n\n".join(results)


# ─── 2. Get Project RFIs ─────────────────────────────────────────────────────


def get_project_rfis(db: Session, project_id: int, **kwargs) -> str:
    """Fetch all RFIs for a project with status summary."""
    rfis = db.query(RFI).filter(RFI.project_id == project_id).all()

    if not rfis:
        return "No RFIs found for this project."

    status_counts = {}
    for r in rfis:
        s = r.status.value if hasattr(r.status, "value") else str(r.status)
        status_counts[s] = status_counts.get(s, 0) + 1

    summary = f"Total RFIs: {len(rfis)}\n"
    summary += "Status breakdown: " + ", ".join(f"{k}: {v}" for k, v in status_counts.items()) + "\n\n"

    for r in rfis[:20]:
        status = r.status.value if hasattr(r.status, "value") else str(r.status)
        overdue = ""
        if r.due_date and r.due_date < datetime.utcnow() and status == "OPEN":
            overdue = " [OVERDUE]"
        summary += f"  RFI #{r.id}: {r.title} [{status}]{overdue}"
        if r.discipline:
            summary += f" | {r.discipline}"
        summary += "\n"

    return summary


# ─── 3. Get Project Risks ────────────────────────────────────────────────────


def get_project_risks(db: Session, project_id: int, **kwargs) -> str:
    """Fetch all risks with severity breakdown."""
    risks = db.query(Risk).filter(Risk.project_id == project_id).all()

    if not risks:
        return "No risks recorded for this project."

    severity_counts = {}
    for r in risks:
        s = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
        severity_counts[s] = severity_counts.get(s, 0) + 1

    summary = f"Total Risks: {len(risks)}\n"
    summary += "Severity breakdown: " + ", ".join(f"{k}: {v}" for k, v in severity_counts.items()) + "\n\n"

    for r in risks[:20]:
        sev = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
        status = r.status.value if hasattr(r.status, "value") else str(r.status)
        score = ""
        if r.impact_score and r.probability_score:
            score = f" | Score: {r.impact_score * r.probability_score:.1f}"
        summary += f"  Risk #{r.id}: {r.title} [{sev}/{status}]{score}"
        if r.detected_by:
            summary += f" (by {r.detected_by})"
        summary += "\n"

    return summary


# ─── 4. Get Document Full Text ───────────────────────────────────────────────


def get_document_full_text(db: Session, document_id: int, **kwargs) -> str:
    """Reconstruct the full text of a document from its chunks."""
    chunks = (
        db.query(DocChunk)
        .filter(DocChunk.document_id == document_id)
        .order_by(DocChunk.chunk_index)
        .all()
    )

    if not chunks:
        return f"No text found for document ID {document_id}. It may not be processed yet."

    full_text = "\n\n".join(c.text for c in chunks)

    # Get the filename
    doc = db.query(Document).filter(Document.id == document_id).first()
    filename = "unknown"
    if doc:
        media = db.query(Media).filter(Media.id == doc.media_id).first()
        if media:
            filename = media.filename

    # Truncate to ~15000 chars to stay within LLM context limits
    if len(full_text) > 15000:
        full_text = full_text[:15000] + "\n\n[... TRUNCATED — document continues ...]"

    return f"Document: {filename} ({len(chunks)} chunks, {len(full_text)} chars)\n\n{full_text}"


# ─── 5. Create RFI ───────────────────────────────────────────────────────────


def create_rfi(
    db: Session,
    project_id: int,
    created_by: int,
    title: str,
    description: str,
    discipline: str = "General",
    zone: str = None,
    **kwargs,
) -> str:
    """Create a new RFI record in the database."""
    rfi = RFI(
        project_id=project_id,
        title=title[:200],
        description=description,
        status=RfiStatus.OPEN,
        discipline=discipline,
        zone=zone,
        created_by=created_by,
        created_at=datetime.utcnow(),
    )
    db.add(rfi)
    db.commit()
    db.refresh(rfi)

    return f"RFI #{rfi.id} created: {rfi.title}"


# ─── 6. Create Risk ──────────────────────────────────────────────────────────


def create_risk(
    db: Session,
    project_id: int,
    title: str,
    description: str,
    severity: str = "MEDIUM",
    discipline: str = "General",
    impact_score: float = 5.0,
    probability_score: float = 5.0,
    mitigation: str = "",
    **kwargs,
) -> str:
    """Create a new AI-detected risk record."""
    # Validate severity
    try:
        sev_enum = RiskSeverity(severity.upper())
    except (ValueError, KeyError):
        sev_enum = RiskSeverity.MEDIUM

    risk = Risk(
        project_id=project_id,
        title=title[:200],
        description=description,
        severity=sev_enum,
        status=RiskStatus.OPEN,
        discipline=discipline,
        impact_score=min(max(float(impact_score), 1.0), 10.0),
        probability_score=min(max(float(probability_score), 1.0), 10.0),
        mitigation=mitigation,
        detected_by="AI",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    sev_str = sev_enum.value
    return f"Risk #{risk.id} created: {risk.title} [{sev_str}]"


# ─── 7. Get Project Schedule ─────────────────────────────────────────────────


def get_project_schedule(db: Session, project_id: int, **kwargs) -> str:
    """Fetch schedule items with delay analysis."""
    items = (
        db.query(ScheduleItem)
        .filter(ScheduleItem.project_id == project_id)
        .order_by(ScheduleItem.planned_start)
        .all()
    )

    if not items:
        return "No schedule items found for this project."

    now = datetime.utcnow()
    lines = [f"Schedule: {len(items)} tasks\n"]

    delayed = 0
    for si in items:
        delay_days = 0
        status_tag = ""

        if si.actual_end:
            # Completed task — check if it finished late
            delta = (si.actual_end - si.planned_end).days
            if delta > 0:
                status_tag = f" [LATE by {delta}d]"
                delayed += 1
            else:
                status_tag = " [ON TIME]"
        elif si.actual_start and not si.actual_end:
            # In progress — check if overdue
            if now > si.planned_end:
                delta = (now - si.planned_end).days
                status_tag = f" [OVERDUE by {delta}d]"
                delayed += 1
            else:
                status_tag = f" [IN PROGRESS {si.progress_pct:.0f}%]"
        else:
            # Not started
            if now > si.planned_start:
                delta = (now - si.planned_start).days
                status_tag = f" [NOT STARTED, {delta}d behind]"
                delayed += 1
            else:
                status_tag = " [UPCOMING]"

        lines.append(
            f"  {si.task_name}{status_tag} | "
            f"Planned: {si.planned_start.strftime('%Y-%m-%d')} → {si.planned_end.strftime('%Y-%m-%d')} | "
            f"Progress: {si.progress_pct:.0f}%"
        )

    lines.insert(1, f"Delayed/Overdue: {delayed}/{len(items)}\n")
    return "\n".join(lines)


# ─── 8. Get Project Cost Summary ─────────────────────────────────────────────


def get_project_cost_summary(db: Session, project_id: int, **kwargs) -> str:
    """Aggregate cost lines by category with variance analysis."""
    rows = (
        db.query(
            CostLine.category,
            func.sum(CostLine.budgeted).label("total_budget"),
            func.sum(CostLine.actual).label("total_actual"),
        )
        .filter(CostLine.project_id == project_id)
        .group_by(CostLine.category)
        .all()
    )

    if not rows:
        return "No cost data found for this project."

    lines = ["Cost Summary by Category:\n"]
    total_budget = 0
    total_actual = 0
    over_budget_cats = []

    for cat, budget, actual in rows:
        budget = float(budget or 0)
        actual = float(actual or 0)
        total_budget += budget
        total_actual += actual

        variance = actual - budget
        variance_pct = (variance / budget * 100) if budget > 0 else 0
        flag = " ⚠ OVER BUDGET" if variance > 0 else ""

        if variance > 0:
            over_budget_cats.append((cat, variance_pct))

        lines.append(
            f"  {cat}: Budget ${budget:,.0f} | Actual ${actual:,.0f} | "
            f"Variance {variance_pct:+.1f}%{flag}"
        )

    # Totals
    total_var = total_actual - total_budget
    total_var_pct = (total_var / total_budget * 100) if total_budget > 0 else 0

    lines.append(f"\nTOTAL: Budget ${total_budget:,.0f} | Actual ${total_actual:,.0f} | Variance {total_var_pct:+.1f}%")

    if over_budget_cats:
        lines.append(f"\n{len(over_budget_cats)} categories over budget: " +
                      ", ".join(f"{c} ({p:+.1f}%)" for c, p in over_budget_cats))

    return "\n".join(lines)


# ─── Tool Registry Builder ───────────────────────────────────────────────────


def build_tool_registry(db: Session, project_id: int, user_id: int) -> Dict[str, Tool]:
    """Build the complete set of agent tools, pre-bound with project/user context."""

    tools = [
        Tool(
            name="search_project_documents",
            description="Semantic search across project documents. Returns relevant text chunks.",
            parameters={"query": "str — search query", "limit": "int — max results (default 5)"},
            fn=search_project_documents,
        ),
        Tool(
            name="get_project_rfis",
            description="List all RFIs for the project with status counts and overdue flags.",
            parameters={"project_id": "int"},
            fn=get_project_rfis,
        ),
        Tool(
            name="get_project_risks",
            description="List all risks for the project with severity breakdown and scores.",
            parameters={"project_id": "int"},
            fn=get_project_risks,
        ),
        Tool(
            name="get_document_full_text",
            description="Get the full text content of a specific document by its ID.",
            parameters={"document_id": "int"},
            fn=get_document_full_text,
        ),
        Tool(
            name="create_rfi",
            description="Create a new RFI (Request for Information) for an ambiguous or missing contract clause.",
            parameters={
                "title": "str — short title",
                "description": "str — detailed description of what needs clarification",
                "discipline": "str — e.g. Structural, MEP, Architectural, General",
                "zone": "str (optional) — project zone",
            },
            fn=create_rfi,
        ),
        Tool(
            name="create_risk",
            description="Create a new AI-detected risk record for the project.",
            parameters={
                "title": "str — short risk title",
                "description": "str — detailed risk description",
                "severity": "str — LOW, MEDIUM, HIGH, or CRITICAL",
                "discipline": "str — e.g. Structural, Legal, Financial, Schedule",
                "impact_score": "float — 1.0 to 10.0",
                "probability_score": "float — 1.0 to 10.0",
                "mitigation": "str — suggested mitigation strategy",
            },
            fn=create_risk,
        ),
        Tool(
            name="get_project_schedule",
            description="Get project schedule with delay analysis for each task.",
            parameters={"project_id": "int"},
            fn=get_project_schedule,
        ),
        Tool(
            name="get_project_cost_summary",
            description="Get cost breakdown by category with budget vs actual variance.",
            parameters={"project_id": "int"},
            fn=get_project_cost_summary,
        ),
    ]

    return {t.name: t for t in tools}

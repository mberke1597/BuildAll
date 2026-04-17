"""
Dashboard API — Project Command Center endpoints.
Powers the project-specific dashboard with KPIs, charts, and drilldowns.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import (
    DailyReport,
    Project,
    ProjectMember,
    RFI,
    Risk,
    Role,
    User,
)
from app.schemas import (
    DailyReportOut,
    DashboardResponse,
    RfiOut,
    RiskItem,
)
from app.services.analyzer import build_dashboard
from app.services.seed_dashboard import seed_dashboard_data

router = APIRouter(prefix="/projects", tags=["dashboard"])


def _ensure_access(db: Session, project_id: int, user: User):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.company_id == user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    return project


@router.get("/{project_id}/dashboard", response_model=DashboardResponse)
def get_project_dashboard(
    project_id: int,
    date_from: Optional[str] = Query(None, alias="from", description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, alias="to", description="ISO date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full dashboard payload for a project — all sections in one call."""
    _ensure_access(db, project_id, user)

    from_dt = datetime.fromisoformat(date_from) if date_from else None
    to_dt = datetime.fromisoformat(date_to) if date_to else None

    return build_dashboard(db, project_id, from_dt, to_dt)


@router.get("/{project_id}/rfis", response_model=list[RfiOut])
def list_rfis(
    project_id: int,
    status: Optional[str] = Query(None),
    discipline: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List RFIs for a project with optional filters."""
    _ensure_access(db, project_id, user)

    q = db.query(RFI).filter(RFI.project_id == project_id)
    if status:
        q = q.filter(RFI.status == status)
    if discipline:
        q = q.filter(RFI.discipline == discipline)
    if zone:
        q = q.filter(RFI.zone == zone)

    return q.order_by(RFI.created_at.desc()).all()


@router.get("/{project_id}/risks", response_model=list[RiskItem])
def list_risks(
    project_id: int,
    severity: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List risks for a project with optional filters."""
    _ensure_access(db, project_id, user)

    q = db.query(Risk).filter(Risk.project_id == project_id)
    if severity:
        q = q.filter(Risk.severity == severity)
    if zone:
        q = q.filter(Risk.zone == zone)

    return q.order_by(Risk.severity.desc(), Risk.created_at.desc()).all()


@router.get("/{project_id}/daily-reports", response_model=list[DailyReportOut])
def list_daily_reports(
    project_id: int,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List daily reports for a project with optional date range."""
    _ensure_access(db, project_id, user)

    q = db.query(DailyReport).filter(DailyReport.project_id == project_id)
    if date_from:
        q = q.filter(DailyReport.report_date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(DailyReport.report_date <= datetime.fromisoformat(date_to))

    return q.order_by(DailyReport.report_date.desc()).limit(100).all()


@router.post("/{project_id}/seed-dashboard")
def seed_demo_dashboard(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Seed demo dashboard data for a project (ADMIN only)."""
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")
    _ensure_access(db, project_id, user)
    seed_dashboard_data(db, project_id, user.id)
    return {"status": "ok", "message": "Demo dashboard data seeded"}

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Project,
    ProjectMember,
    Role,
    User,
    Message,
    Document,
    Media,
    AuditLog,
)
from app.schemas import ProjectAnalyticsOut, AuditLogOut

router = APIRouter(prefix="/projects", tags=["analytics"])


def _ensure_access(db: Session, user: User, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
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


@router.get("/{project_id}/analytics", response_model=ProjectAnalyticsOut)
def project_analytics(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_access(db, user, project_id)
    messages_count = db.query(func.count(Message.id)).filter(Message.project_id == project_id).scalar() or 0
    documents_count = db.query(func.count(Document.id)).filter(Document.project_id == project_id).scalar() or 0
    media_count = db.query(func.count(Media.id)).filter(Media.project_id == project_id).scalar() or 0

    last_msg = (
        db.query(Message.created_at)
        .filter(Message.project_id == project_id)
        .order_by(Message.created_at.desc())
        .first()
    )
    last_doc = (
        db.query(Document.created_at)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .first()
    )
    last_activity: Optional[datetime] = None
    if last_msg and last_doc:
        last_activity = max(last_msg[0], last_doc[0])
    elif last_msg:
        last_activity = last_msg[0]
    elif last_doc:
        last_activity = last_doc[0]

    return ProjectAnalyticsOut(
        project_id=project_id,
        messages_count=messages_count,
        documents_count=documents_count,
        media_count=media_count,
        last_activity=last_activity,
    )


@router.get("/{project_id}/audit-logs", response_model=list[AuditLogOut])
def project_audit_logs(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_access(db, user, project_id)
    return (
        db.query(AuditLog)
        .filter(AuditLog.company_id == user.company_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Project, ProjectMember, ProjectNote, ProjectNoteKind, Role, User
from app.schemas import ParcelLookupIn

router = APIRouter(prefix="/projects", tags=["parcel"])


@router.post("/{project_id}/parcel-lookup")
def parcel_lookup(
    project_id: int,
    payload: ParcelLookupIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    note = ProjectNote(
        project_id=project_id,
        created_by=user.id,
        kind=ProjectNoteKind.PARCEL_LOOKUP,
        content=payload.content,
    )
    db.add(note)
    db.commit()
    return {"status": "saved"}

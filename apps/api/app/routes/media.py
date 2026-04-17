import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.config import get_settings
from app.core.audit import log_audit
from app.db.session import get_db
from app.models import Media, Project, ProjectMember, Role, User, Message, MessageType
from app.schemas import MediaOut
from app.services.storage import upload_bytes, ensure_bucket
from app.services.storage import get_presigned_url

router = APIRouter(prefix="/projects", tags=["media"])


def _upload_media(
    project_id: int,
    file: UploadFile,
    db: Session,
    user: User,
    create_message: bool = True,
) -> Media:
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")

    settings = get_settings()
    content = file.file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")

    allowed_types = {"application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     "audio/webm", "audio/mpeg", "audio/mp4", "audio/wav", "image/png", "image/jpeg"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    ensure_bucket()
    key = f"{project_id}/{uuid.uuid4()}-{file.filename}"
    upload_bytes(key, content, file.content_type)
    media = Media(
        company_id=user.company_id,
        project_id=project_id,
        storage_key=key,
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    log_audit(db, company_id=user.company_id, user_id=user.id, action="FILE_UPLOAD", meta={"media_id": media.id})

    if create_message:
        msg_type = MessageType.VOICE if file.content_type.startswith("audio/") else MessageType.FILE
        msg = Message(project_id=project_id, sender_id=user.id, type=msg_type, media_id=media.id)
        db.add(msg)
        db.commit()
    return media


@router.post("/{project_id}/upload", response_model=MediaOut)
def upload_media(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _upload_media(project_id, file, db, user, create_message=True)


@router.get("/{project_id}/media/{media_id}")
def get_media_url(
    project_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    media = (
        db.query(Media)
        .filter(Media.id == media_id, Media.project_id == project_id, Media.company_id == user.company_id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    url = get_presigned_url(media.storage_key)
    return {"url": url, "filename": media.filename}

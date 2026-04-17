from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Document, DocumentStatus, Project, ProjectMember, Role, User, Media
from app.schemas import DocumentOut
from app.routes.media import _upload_media
from app.services.queue import get_queue

router = APIRouter(prefix="/projects", tags=["documents"])


@router.post("/{project_id}/documents/upload", response_model=DocumentOut)
def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    media = _upload_media(project_id, file, db, user, create_message=False)
    document = Document(project_id=project_id, media_id=media.id, status=DocumentStatus.UPLOADED)
    db.add(document)
    db.commit()
    db.refresh(document)
    queue = get_queue()
    queue.enqueue("worker.tasks.process_document", document.id)
    return document


@router.get("/{project_id}/documents")
def list_documents(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == Role.CLIENT:
        member = db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first()
        if not member:
            raise HTTPException(status_code=403, detail="Forbidden")
    
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    result = []
    for doc in docs:
        media = db.query(Media).filter(Media.id == doc.media_id).first() if doc.media_id else None
        result.append({
            "id": doc.id,
            "status": doc.status.value,
            "created_at": doc.created_at,
            "error": doc.error,
            "media_id": doc.media_id,
            "filename": media.filename if media else f"Document #{doc.id}"
        })
    return result


@router.delete("/{project_id}/documents/{document_id}")
def delete_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id, Project.company_id == user.company_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.project_id == project_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete associated chunks from doc_chunks table
    from app.models import DocChunk
    db.query(DocChunk).filter(DocChunk.document_id == document_id).delete()
    
    # Delete the document
    db.delete(document)
    db.commit()
    
    from app.core.audit import log_audit
    log_audit(db, company_id=user.company_id, user_id=user.id, action="DOCUMENT_DELETE", meta={"document_id": document_id})
    
    return {"status": "deleted", "document_id": document_id}

"""
BuildAll Worker Tasks

1. process_document(document_id) — Extract text, chunk, embed, store
2. generate_project_digest(project_id) — Weekly AI digest
3. process_agent_task(run_id) — Execute an autonomous agent in the background
"""
import io
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber
from docx import Document as DocxDocument
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentStatus, DocChunk, Media
from app.services.ai import get_ai_provider
from app.services.documents import chunk_text
from app.services.storage import get_s3_client
from app.core.audit import log_audit


# ─── Document Processing ─────────────────────────────────────────────────────


def _download_media(media: Media) -> bytes:
    settings = get_settings()
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.minio_bucket, Key=media.storage_key)
    return obj["Body"].read()


def _extract_text_pdf(content: bytes) -> List[Tuple[str, Optional[int]]]:
    pages: List[Tuple[str, Optional[int]]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((text, i + 1))
    return pages


def _extract_text_docx(content: bytes) -> List[Tuple[str, Optional[int]]]:
    doc = DocxDocument(io.BytesIO(content))
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return [(text, None)] if text else []


def _extract_text_txt(content: bytes) -> List[Tuple[str, Optional[int]]]:
    text = content.decode("utf-8", errors="ignore")
    return [(text, None)] if text.strip() else []


def process_document(document_id: int):
    db: Session = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        media = db.query(Media).filter(Media.id == doc.media_id).first()
        if not media:
            doc.status = DocumentStatus.FAILED
            doc.error = "Media not found"
            db.commit()
            return

        content = _download_media(media)
        pages: List[Tuple[str, Optional[int]]] = []

        if media.content_type == "application/pdf":
            pages = _extract_text_pdf(content)
        elif media.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            pages = _extract_text_docx(content)
        elif media.content_type == "text/plain":
            pages = _extract_text_txt(content)
        else:
            doc.status = DocumentStatus.FAILED
            doc.error = "Unsupported document type"
            db.commit()
            return

        ai = get_ai_provider()
        chunks: List[Tuple[str, Optional[int]]] = []
        for page_text, page_num in pages:
            for ch in chunk_text(page_text):
                chunks.append((ch, page_num))

        if not chunks:
            doc.status = DocumentStatus.FAILED
            doc.error = "No text extracted"
            db.commit()
            return

        embeddings = ai.embed([c[0] for c in chunks])

        for i, (ch, page_num) in enumerate(chunks):
            dc = DocChunk(
                document_id=doc.id,
                chunk_index=i,
                text=ch,
                page_number=page_num,
                embedding=embeddings[i],
            )
            db.add(dc)

        doc.status = DocumentStatus.READY
        doc.processed_at = datetime.utcnow()
        db.commit()
        log_audit(db, company_id=media.company_id, user_id=None, action="DOC_INDEXED", meta={"document_id": doc.id})
    except Exception as e:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error = str(e)
            db.commit()
    finally:
        db.close()


# ─── Project Digest ──────────────────────────────────────────────────────────


def generate_project_digest(project_id: int):
    """
    Proactive assistance: Generate a weekly AI summary for a project.
    """
    from app.models import Project, ProjectNote, ProjectNoteKind

    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        recent_docs = (
            db.query(Document)
            .filter(Document.project_id == project_id, Document.status == DocumentStatus.READY)
            .order_by(Document.processed_at.desc())
            .limit(10)
            .all()
        )

        recent_media = (
            db.query(Media)
            .filter(Media.project_id == project_id)
            .order_by(Media.created_at.desc())
            .limit(5)
            .all()
        )

        if not recent_docs and not recent_media:
            return

        summary_input = f"Project: {project.name}\nLocation: {project.location or 'N/A'}\n\n"
        summary_input += f"Recent documents ({len(recent_docs)}):\n"
        for doc in recent_docs:
            media = db.query(Media).filter(Media.id == doc.media_id).first()
            if media:
                summary_input += f"- {media.filename} (processed: {doc.processed_at})\n"

        summary_input += f"\nRecent uploads ({len(recent_media)}):\n"
        for m in recent_media:
            summary_input += f"- {m.filename} ({m.content_type}, {m.created_at})\n"

        try:
            ai = get_ai_provider()
            digest = ai.chat(
                "You are a construction project assistant. Generate a brief weekly digest "
                "summarizing project activity and suggesting next steps. Be concise and actionable.",
                summary_input,
            )
        except Exception:
            return

        note = ProjectNote(
            project_id=project_id,
            created_by=project.created_by,
            kind=ProjectNoteKind.PARCEL_LOOKUP,
            content=f"## Weekly AI Digest\n\n{digest}",
        )
        db.add(note)
        db.commit()

    except Exception:
        pass
    finally:
        db.close()


# ─── Agent Task Execution ────────────────────────────────────────────────────


def process_agent_task(run_id: int):
    """
    Execute an agent in the background.

    Called by RQ worker when an async agent run is enqueued.
    Loads the AgentRun from DB, executes the appropriate agent,
    and saves all results (steps, answer, artifacts) back to DB.
    """
    from app.agents.models_extension import AgentRun
    from app.agents.orchestrator import run_agent

    db: Session = SessionLocal()
    try:
        agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not agent_run:
            return

        # Update status to running
        agent_run.status = "running"
        db.commit()

        # Extract parameters
        task = agent_run.task
        agent_type = agent_run.agent_type
        context = agent_run.context_json or {}

        # Ensure context has required fields
        if "project_id" not in context:
            context["project_id"] = agent_run.project_id
        if "user_id" not in context:
            context["user_id"] = agent_run.triggered_by

        # Execute the agent
        result = run_agent(
            task=task,
            agent_type=agent_type,
            context=context,
            db=db,
        )

        # Save results
        agent_run.status = "completed" if result.success else "failed"
        agent_run.answer = result.answer
        agent_run.steps_json = [s.to_dict() for s in result.steps]
        agent_run.artifacts_json = result.artifacts
        agent_run.total_elapsed_ms = result.total_elapsed_ms
        agent_run.error = result.error
        agent_run.completed_at = datetime.utcnow()
        db.commit()

        # Audit log
        log_audit(
            db,
            company_id=None,  # Worker doesn't always have company context
            user_id=agent_run.triggered_by,
            action="AGENT_RUN_COMPLETED",
            meta={
                "run_id": agent_run.id,
                "agent_type": agent_type,
                "success": result.success,
                "artifacts_count": len(result.artifacts),
                "elapsed_ms": result.total_elapsed_ms,
            },
        )

    except Exception as exc:
        # Mark as failed
        try:
            agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if agent_run:
                agent_run.status = "failed"
                agent_run.error = str(exc)[:500]
                agent_run.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

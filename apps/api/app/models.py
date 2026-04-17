import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Boolean,
    LargeBinary,
    Float,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import BYTEA, UUID

from app.db.base import Base


class VectorType(TypeDecorator):
    impl = BYTEA
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(1536))
        return dialect.type_descriptor(Text)


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    CONSULTANT = "CONSULTANT"
    CLIENT = "CLIENT"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class MessageType(str, enum.Enum):
    TEXT = "TEXT"
    FILE = "FILE"
    VOICE = "VOICE"


class ProjectNoteKind(str, enum.Enum):
    PARCEL_LOOKUP = "PARCEL_LOOKUP"


class RfiStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    CLOSED = "CLOSED"
    OVERDUE = "OVERDUE"


class RiskSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskStatus(str, enum.Enum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    creator = relationship("User")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_in_project = Column(String, nullable=True)

    project = relationship("Project")
    user = relationship("User")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    storage_key = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(MessageType), nullable=False)
    text = Column(Text, nullable=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    media = relationship("Media")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=False)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    media = relationship("Media")


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    embedding = Column(VectorType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProjectNote(Base):
    __tablename__ = "project_notes"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(Enum(ProjectNoteKind), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CostCatalog(Base):
    __tablename__ = "cost_catalog"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    quality_level = Column(String, nullable=False)
    unit_cost_per_m2 = Column(Float, nullable=False)
    location_multiplier_default = Column(Float, nullable=False, default=1.0)


# ---------- Dashboard: RFIs, Risks, DailyReports, Schedule, CostLines ----------


class RFI(Base):
    __tablename__ = "rfis"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(RfiStatus), nullable=False, default=RfiStatus.OPEN)
    discipline = Column(String, nullable=True)  # e.g. Structural, MEP, Architectural
    zone = Column(String, nullable=True)  # e.g. Zone A, Zone B
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_date = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project")


class Risk(Base):
    __tablename__ = "risks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(Enum(RiskSeverity), nullable=False, default=RiskSeverity.MEDIUM)
    status = Column(Enum(RiskStatus), nullable=False, default=RiskStatus.OPEN)
    discipline = Column(String, nullable=True)
    zone = Column(String, nullable=True)
    impact_score = Column(Float, nullable=True)  # 1-10
    probability_score = Column(Float, nullable=True)  # 1-10
    mitigation = Column(Text, nullable=True)
    detected_by = Column(String, nullable=True)  # "AI" or "USER"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    report_date = Column(DateTime, nullable=False)
    weather = Column(String, nullable=True)
    workers_count = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    issues_count = Column(Integer, nullable=False, default=0)
    safety_incidents = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project")


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_name = Column(String, nullable=False)
    discipline = Column(String, nullable=True)
    planned_start = Column(DateTime, nullable=False)
    planned_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    progress_pct = Column(Float, nullable=False, default=0)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project")


class CostLine(Base):
    __tablename__ = "cost_lines"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    category = Column(String, nullable=False)  # e.g. Labor, Material, Equipment, Subcontractor
    discipline = Column(String, nullable=True)
    description = Column(String, nullable=True)
    budgeted = Column(Float, nullable=False, default=0)
    actual = Column(Float, nullable=False, default=0)
    period_date = Column(DateTime, nullable=False)  # e.g. month bucket
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project")


# ---------- Chat V2: Sessions, Messages, Feedback, Usage, Config ----------


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")
    project = relationship("Project")
    messages = relationship("AssistantMessage", back_populates="session", order_by="AssistantMessage.created_at")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)  # [{media_id, filename, content_type}]
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("ChatSession", back_populates="messages")
    feedbacks = relationship("ChatFeedback", back_populates="message")


class ChatFeedback(Base):
    __tablename__ = "chat_feedback"

    id = Column(Integer, primary_key=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("assistant_messages.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # +1 or -1
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("AssistantMessage", back_populates="feedbacks")
    user = relationship("User")


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CompanyAIConfig(Base):
    __tablename__ = "company_ai_config"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    system_prompt = Column(Text, nullable=True)
    persona_name = Column(String, nullable=True)
    temperature = Column(Float, nullable=False, default=0.2)
    max_tokens_per_response = Column(Integer, nullable=True)
    allowed_topics = Column(JSON, nullable=True)  # list of strings
    preferred_language = Column(String, nullable=True)
    rate_limit_per_hour = Column(Integer, nullable=True, default=30)
    monthly_budget_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company")

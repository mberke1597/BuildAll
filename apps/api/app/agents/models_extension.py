"""
AgentRun model — stores the full audit trail of every agent execution.

Each run records: task, steps (scratchpad), answer, artifacts created,
timing, and status. This enables full transparency and debugging.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_type = Column(String, nullable=False)  # "document_analyst", "risk_monitor", "cost_advisor"
    status = Column(String, nullable=False, default="pending")  # pending / running / completed / failed
    task = Column(Text, nullable=False)
    context_json = Column(JSON, nullable=True)  # {document_id, project_id, etc.}
    steps_json = Column(JSON, nullable=True)  # List[Step.to_dict()] — full scratchpad
    answer = Column(Text, nullable=True)
    artifacts_json = Column(JSON, nullable=True)  # [{type, id, title}, ...] — created RFIs/Risks
    total_elapsed_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project")
    user = relationship("User", foreign_keys=[triggered_by])

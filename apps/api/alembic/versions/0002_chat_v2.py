"""add chat v2 tables: sessions, messages, feedback, usage, ai_config

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Chat sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])

    # Assistant messages (conversation turns)
    op.create_table(
        "assistant_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", sa.JSON, nullable=True),
        sa.Column("attachments", sa.JSON, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_assistant_messages_session_id", "assistant_messages", ["session_id"])

    # Chat feedback (thumbs up/down)
    op.create_table(
        "chat_feedback",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("assistant_messages.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_chat_feedback_message_id", "chat_feedback", ["message_id"])

    # AI usage tracking
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_ai_usage_company_id", "ai_usage", ["company_id"])

    # Company AI config (admin-configurable prompts, rate limits, etc.)
    op.create_table(
        "company_ai_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("persona_name", sa.String, nullable=True),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.2"),
        sa.Column("max_tokens_per_response", sa.Integer, nullable=True),
        sa.Column("allowed_topics", sa.JSON, nullable=True),
        sa.Column("preferred_language", sa.String, nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer, nullable=True, server_default="30"),
        sa.Column("monthly_budget_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("company_ai_config")
    op.drop_table("ai_usage")
    op.drop_table("chat_feedback")
    op.drop_table("assistant_messages")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_project_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

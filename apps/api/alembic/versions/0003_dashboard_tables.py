"""add dashboard tables: rfis, risks, daily_reports, schedule_items, cost_lines

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # RFIs
    op.create_table(
        "rfis",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="OPEN"),
        sa.Column("discipline", sa.String, nullable=True),
        sa.Column("zone", sa.String, nullable=True),
        sa.Column("assigned_to", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_date", sa.DateTime, nullable=True),
        sa.Column("closed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_rfis_project_id", "rfis", ["project_id"])

    # Risks
    op.create_table(
        "risks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String, nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String, nullable=False, server_default="OPEN"),
        sa.Column("discipline", sa.String, nullable=True),
        sa.Column("zone", sa.String, nullable=True),
        sa.Column("impact_score", sa.Float, nullable=True),
        sa.Column("probability_score", sa.Float, nullable=True),
        sa.Column("mitigation", sa.Text, nullable=True),
        sa.Column("detected_by", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_risks_project_id", "risks", ["project_id"])

    # Daily Reports
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("report_date", sa.DateTime, nullable=False),
        sa.Column("weather", sa.String, nullable=True),
        sa.Column("workers_count", sa.Integer, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("issues_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("safety_incidents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_daily_reports_project_id", "daily_reports", ["project_id"])

    # Schedule Items
    op.create_table(
        "schedule_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_name", sa.String, nullable=False),
        sa.Column("discipline", sa.String, nullable=True),
        sa.Column("planned_start", sa.DateTime, nullable=False),
        sa.Column("planned_end", sa.DateTime, nullable=False),
        sa.Column("actual_start", sa.DateTime, nullable=True),
        sa.Column("actual_end", sa.DateTime, nullable=True),
        sa.Column("progress_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_schedule_items_project_id", "schedule_items", ["project_id"])

    # Cost Lines
    op.create_table(
        "cost_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("discipline", sa.String, nullable=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("budgeted", sa.Float, nullable=False, server_default="0"),
        sa.Column("actual", sa.Float, nullable=False, server_default="0"),
        sa.Column("period_date", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_cost_lines_project_id", "cost_lines", ["project_id"])


def downgrade():
    op.drop_table("cost_lines")
    op.drop_table("schedule_items")
    op.drop_table("daily_reports")
    op.drop_table("risks")
    op.drop_table("rfis")

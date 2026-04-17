"""
RiskMonitorAgent — Proactive project health scanning.

Checks schedule delays, cost overruns, overdue RFIs, and creates
Risk records for any findings. Returns an executive risk summary.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentResult, BaseAgent, Tool
from app.agents.prompts import RISK_MONITOR_PROMPT
from app.agents.tools import build_tool_registry


class RiskMonitorAgent(BaseAgent):
    """Proactive risk monitoring agent."""

    def __init__(self, tools: dict[str, Tool]):
        super().__init__(
            tools=list(tools.values()),
            system_prompt=RISK_MONITOR_PROMPT,
            max_steps=12,
        )

    @classmethod
    def scan_project(
        cls,
        project_id: int,
        user_id: int,
        db: Session,
    ) -> AgentResult:
        """
        Comprehensive project health scan.

        Checks:
          - Schedule: delayed/overdue tasks
          - Cost: budget overruns by category
          - RFIs: overdue/stale items
          - Existing risks: avoid duplicates
        """
        tools = build_tool_registry(db, project_id, user_id)
        agent = cls(tools=tools)

        task = f"""Perform a comprehensive risk scan for project ID {project_id}.

Steps you MUST follow:
1. Call get_project_schedule to analyze schedule health.
   Flag any tasks that are delayed >7 days.
2. Call get_project_cost_summary to check budget health.
   Flag any category >10% over budget.
3. Call get_project_rfis to check for overdue or stale RFIs.
4. Call get_project_risks to see existing risks (avoid duplicates).
5. For EACH new issue found, call create_risk with appropriate severity:
   - >30 day delay or >25% overrun → CRITICAL
   - >14 day delay or >15% overrun → HIGH
   - >7 day delay or >10% overrun → MEDIUM
   - Minor concerns → LOW
6. Provide a final_answer with:
   - Project Health Score (0-100)
   - Total new risks created
   - Top 3 immediate concerns
   - Recommended actions for the project team"""

        context = {
            "project_id": project_id,
            "user_id": user_id,
        }

        return agent.run(task, context, db)

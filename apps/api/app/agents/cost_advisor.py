"""
CostAdvisorAgent — Financial analysis and budget intelligence.

Analyzes cost lines, calculates burn rate, projects final cost,
and flags financial risks.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentResult, BaseAgent, Tool
from app.agents.prompts import COST_ADVISOR_PROMPT
from app.agents.tools import build_tool_registry


class CostAdvisorAgent(BaseAgent):
    """Construction cost analyst agent."""

    def __init__(self, tools: dict[str, Tool]):
        super().__init__(
            tools=list(tools.values()),
            system_prompt=COST_ADVISOR_PROMPT,
            max_steps=10,
        )

    @classmethod
    def analyze_costs(
        cls,
        project_id: int,
        user_id: int,
        db: Session,
    ) -> AgentResult:
        """Full cost analysis with projected final cost and risk flagging."""
        tools = build_tool_registry(db, project_id, user_id)
        agent = cls(tools=tools)

        task = f"""Perform a complete cost analysis for project ID {project_id}.

Steps:
1. Call get_project_cost_summary for budget breakdown.
2. Call get_project_schedule to correlate cost with schedule progress.
3. Call get_project_risks to check existing financial risks.
4. Optionally search documents for payment terms or penalty clauses.
5. For significant findings (>15% overrun), call create_risk.
6. Provide a final_answer with:
   - Budget status: on track / at risk / over budget
   - Projected final cost (Estimate at Completion)
   - Top 3 cost concerns
   - Recommended actions"""

        context = {
            "project_id": project_id,
            "user_id": user_id,
        }

        return agent.run(task, context, db)

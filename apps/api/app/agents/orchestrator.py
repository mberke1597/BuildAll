"""
OrchestratorAgent — Routes tasks to specialized agents.
Provides the top-level run_agent() convenience function
used by routes and worker tasks.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict

from sqlalchemy.orm import Session

from app.agents.base import AgentResult


class AgentType(str, Enum):
    DOCUMENT_ANALYST = "document_analyst"
    RISK_MONITOR = "risk_monitor"
    COST_ADVISOR = "cost_advisor"


class OrchestratorAgent:
    """Routes tasks to the appropriate specialized agent."""

    def run(
        self,
        task: str,
        agent_type: AgentType,
        context: Dict,
        db: Session,
    ) -> AgentResult:
        project_id = context.get("project_id")
        user_id = context.get("user_id")

        if not project_id or not user_id:
            return AgentResult(
                success=False,
                answer="Missing project_id or user_id in context.",
                steps=[],
                error="Missing required context fields.",
            )

        if agent_type == AgentType.DOCUMENT_ANALYST:
            from app.agents.document_analyst import DocumentAnalystAgent

            document_id = context.get("document_id")
            if document_id:
                return DocumentAnalystAgent.analyze_document(
                    document_id=document_id,
                    project_id=project_id,
                    user_id=user_id,
                    db=db,
                )
            else:
                # Free-form question mode
                return DocumentAnalystAgent.search_and_answer(
                    question=task,
                    project_id=project_id,
                    user_id=user_id,
                    db=db,
                )

        elif agent_type == AgentType.RISK_MONITOR:
            from app.agents.risk_monitor import RiskMonitorAgent

            return RiskMonitorAgent.scan_project(
                project_id=project_id,
                user_id=user_id,
                db=db,
            )

        elif agent_type == AgentType.COST_ADVISOR:
            from app.agents.cost_advisor import CostAdvisorAgent

            return CostAdvisorAgent.analyze_costs(
                project_id=project_id,
                user_id=user_id,
                db=db,
            )

        else:
            return AgentResult(
                success=False,
                answer=f"Unknown agent type: {agent_type}",
                steps=[],
                error=f"Invalid agent_type: {agent_type}",
            )


def run_agent(
    task: str,
    agent_type: str,
    context: Dict,
    db: Session,
) -> AgentResult:
    """
    Convenience function called by routes and worker tasks.
    Validates agent_type and delegates to OrchestratorAgent.
    """
    try:
        at = AgentType(agent_type)
    except ValueError:
        return AgentResult(
            success=False,
            answer=f"Invalid agent type: '{agent_type}'. Valid: {[e.value for e in AgentType]}",
            steps=[],
            error=f"Invalid agent_type: {agent_type}",
        )

    orchestrator = OrchestratorAgent()
    return orchestrator.run(task=task, agent_type=at, context=context, db=db)

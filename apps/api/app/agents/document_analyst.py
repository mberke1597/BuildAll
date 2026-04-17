"""
DocumentAnalystAgent — Reads construction documents, creates RFIs for
ambiguous clauses, and flags risks with severity scores.

This is the primary demo agent for YC: upload a contract → get automated
RFIs + Risks in under 2 minutes.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentResult, BaseAgent, Tool
from app.agents.prompts import DOCUMENT_ANALYST_PROMPT
from app.agents.tools import build_tool_registry


class DocumentAnalystAgent(BaseAgent):
    """Specialized agent for construction document analysis."""

    def __init__(self, tools: dict[str, Tool]):
        super().__init__(
            tools=list(tools.values()),
            system_prompt=DOCUMENT_ANALYST_PROMPT,
            max_steps=15,  # Documents need more steps: read + N creates
        )

    @classmethod
    def analyze_document(
        cls,
        document_id: int,
        project_id: int,
        user_id: int,
        db: Session,
    ) -> AgentResult:
        """
        Analyze a single document end-to-end.

        Flow:
          1. Read full document text
          2. Identify ambiguous/missing clauses → create RFIs
          3. Identify risk factors → create Risks
          4. Return executive summary
        """
        tools = build_tool_registry(db, project_id, user_id)
        agent = cls(tools=tools)

        task = f"""Analyze document ID {document_id} for project ID {project_id}.

Steps you MUST follow:
1. Call get_document_full_text with document_id={document_id} to read the entire document.
2. Carefully read the text and identify ALL ambiguous, missing, or unclear clauses.
   For EACH clause found, call create_rfi with a descriptive title and detailed description.
3. Identify ALL risk factors (penalty clauses, tight deadlines, scope gaps, unclear 
   responsibilities, weather dependencies, liquidated damages, etc.).
   For EACH risk, call create_risk with appropriate severity and scores.
4. After creating all RFIs and Risks, provide a final_answer with:
   - Total RFIs created
   - Total Risks created  
   - Top 3 most critical findings
   - Recommended next steps for the project team

Be thorough. Do not skip creating records — actually call the tools."""

        context = {
            "project_id": project_id,
            "document_id": document_id,
            "user_id": user_id,
        }

        return agent.run(task, context, db)

    @classmethod
    def search_and_answer(
        cls,
        question: str,
        project_id: int,
        user_id: int,
        db: Session,
    ) -> AgentResult:
        """
        Answer a question using project documents as context.
        Lighter-weight than full analysis — just search + answer.
        """
        tools = build_tool_registry(db, project_id, user_id)
        agent = cls(tools=tools)

        task = f"""Answer this question about the project documents:

Question: {question}

Steps:
1. Use search_project_documents to find relevant text chunks.
2. If needed, get_document_full_text for more context.
3. Provide a final_answer with the answer and source references."""

        context = {
            "project_id": project_id,
            "user_id": user_id,
        }

        return agent.run(task, context, db)

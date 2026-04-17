"""
BuildAll Agent Framework — ReAct Loop Engine (Reasoning + Acting)

Each agent follows the loop:
  Think → Act (tool call) → Observe → Think → ... → Final Answer

The scratchpad records every step for full auditability.
No external agent libraries — pure Python + the existing AI service.
"""
from __future__ import annotations

import json
import re
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.ai import get_ai_provider


# ─── Step Types ──────────────────────────────────────────────────────────────


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL = "final"
    ERROR = "error"


@dataclass
class Step:
    type: StepType
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    elapsed_ms: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "elapsed_ms": self.elapsed_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentResult:
    success: bool
    answer: str
    steps: List[Step]
    artifacts: List[Dict] = field(default_factory=list)
    total_elapsed_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "answer": self.answer,
            "steps": [s.to_dict() for s in self.steps],
            "artifacts": self.artifacts,
            "total_elapsed_ms": self.total_elapsed_ms,
            "error": self.error,
        }


# ─── Tool Definition ─────────────────────────────────────────────────────────


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, str]
    fn: Callable


# ─── JSON Response Format Instruction ─────────────────────────────────────────

REACT_FORMAT_INSTRUCTION = """
You MUST respond with ONLY valid JSON. No markdown, no code fences, no extra text.

When you need to call a tool, respond with:
{"thought": "your reasoning about what to do next", "tool_name": "name_of_tool", "tool_args": {"param1": "value1"}}

When you have enough information to give a final answer, respond with:
{"thought": "your final reasoning", "final_answer": "your comprehensive summary and findings"}

Available tools:
{tool_descriptions}

RULES:
- Call ONE tool at a time.
- After receiving an observation, decide if you need more tools or can give a final answer.
- Always create RFIs and Risks by calling the tools — do not just list them in text.
- Be thorough and systematic. Do not rush to a final answer before completing analysis.
- The "final_answer" must be a comprehensive summary of everything you did and found.
"""


# ─── Base Agent Class ─────────────────────────────────────────────────────────


class BaseAgent:
    """
    ReAct agent with a think-act-observe loop.
    Subclass this and provide tools + system_prompt.
    """

    def __init__(
        self,
        tools: List[Tool],
        system_prompt: str,
        max_steps: int = 10,
    ):
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_steps = max_steps

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self, task: str, context: Dict, db: Session) -> AgentResult:
        """Execute the full ReAct loop and return an auditable result."""
        start = time.time()
        steps: List[Step] = []
        artifacts: List[Dict] = []
        successful_steps = 0  # Only count non-error steps toward max

        for iteration in range(self.max_steps * 3):  # Allow more raw iterations for retries
            if successful_steps >= self.max_steps:
                break

            # ── THINK ────────────────────────────────────────────────────
            think_start = time.time()
            try:
                parsed = self._think(task, steps, context)
            except Exception as exc:
                error_msg = str(exc)
                # Rate limit: wait and retry
                if "429" in error_msg or "quota" in error_msg.lower():
                    wait_secs = self._extract_retry_delay(error_msg)
                    steps.append(Step(
                        type=StepType.ERROR,
                        content=f"Rate limited. Waiting {wait_secs}s before retry...",
                        elapsed_ms=int((time.time() - think_start) * 1000),
                    ))
                    time.sleep(wait_secs)
                    continue  # Don't count toward max_steps
                else:
                    steps.append(Step(
                        type=StepType.ERROR,
                        content=f"Think error: {error_msg[:300]}",
                        elapsed_ms=int((time.time() - think_start) * 1000),
                    ))
                    successful_steps += 1
                    continue

            thought = parsed.get("thought", "")
            steps.append(Step(
                type=StepType.THOUGHT,
                content=thought,
                elapsed_ms=int((time.time() - think_start) * 1000),
            ))
            successful_steps += 1

            # ── FINAL ANSWER ─────────────────────────────────────────────
            if "final_answer" in parsed:
                final = parsed["final_answer"]
                steps.append(Step(type=StepType.FINAL, content=final))
                elapsed = int((time.time() - start) * 1000)
                return AgentResult(
                    success=True,
                    answer=final,
                    steps=steps,
                    artifacts=artifacts,
                    total_elapsed_ms=elapsed,
                )

            # ── ACT ──────────────────────────────────────────────────────
            tool_name = parsed.get("tool_name")
            tool_args = parsed.get("tool_args", {})

            if not tool_name or tool_name not in self.tools:
                steps.append(Step(
                    type=StepType.ERROR,
                    content=f"Unknown or missing tool: '{tool_name}'. Available: {list(self.tools.keys())}",
                ))
                continue

            steps.append(Step(
                type=StepType.ACTION,
                content=f"Calling {tool_name}",
                tool_name=tool_name,
                tool_args=tool_args,
            ))

            act_start = time.time()
            observation = self._act(tool_name, tool_args, db, context)
            act_elapsed = int((time.time() - act_start) * 1000)

            steps.append(Step(
                type=StepType.OBSERVATION,
                content=observation,
                tool_name=tool_name,
                elapsed_ms=act_elapsed,
            ))

            # ── Parse artifacts from tool output ─────────────────────────
            self._extract_artifacts(observation, artifacts)

        # ── Max steps reached — force a final answer ─────────────────────
        steps.append(Step(
            type=StepType.ERROR,
            content=f"Max steps ({self.max_steps}) reached. Forcing final answer.",
        ))

        # Ask the LLM for a summary of what was accomplished
        try:
            summary = self._force_final_answer(task, steps, context)
        except Exception:
            summary = self._build_fallback_summary(steps, artifacts)

        elapsed = int((time.time() - start) * 1000)
        return AgentResult(
            success=True,
            answer=summary,
            steps=steps,
            artifacts=artifacts,
            total_elapsed_ms=elapsed,
        )

    # ── Private: Think ───────────────────────────────────────────────────────

    def _think(self, task: str, scratchpad: List[Step], context: Dict) -> Dict:
        """Call the LLM and parse a JSON response. Retry once on parse failure."""
        prompt = self._build_prompt(task, scratchpad, context)
        ai = get_ai_provider()

        raw = ai.chat(self.system_prompt, prompt)
        parsed = self._parse_json(raw)

        if parsed is not None:
            return parsed

        # Retry with explicit error feedback
        retry_prompt = (
            prompt
            + f"\n\n[SYSTEM ERROR] Your last response was not valid JSON. "
            f"Raw output was:\n{raw[:500]}\n\n"
            f"Please respond with ONLY valid JSON. No markdown fences."
        )
        raw2 = ai.chat(self.system_prompt, retry_prompt)
        parsed2 = self._parse_json(raw2)

        if parsed2 is not None:
            return parsed2

        # Fallback: treat it as a thought and ask to continue
        return {"thought": f"(Parse recovery) {raw2[:300]}", "final_answer": raw2[:1000]}

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM output, handling markdown code fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    # ── Private: Act ─────────────────────────────────────────────────────────

    def _act(self, tool_name: str, tool_args: Dict, db: Session, context: Dict) -> str:
        """Execute a tool call, catching all exceptions."""
        tool = self.tools[tool_name]
        try:
            enriched_args = {**tool_args}
            if "project_id" not in enriched_args and "project_id" in context:
                enriched_args["project_id"] = context["project_id"]
            if "created_by" not in enriched_args and "user_id" in context:
                enriched_args["created_by"] = context["user_id"]

            result = tool.fn(db=db, **enriched_args)
            return str(result)
        except Exception as exc:
            return f"[TOOL ERROR] {tool_name} failed: {type(exc).__name__}: {exc}"

    # ── Private: Build Prompt ────────────────────────────────────────────────

    def _build_prompt(self, task: str, scratchpad: List[Step], context: Dict) -> str:
        """Assemble the full user prompt with task, context, and scratchpad."""
        tool_descs = []
        for t in self.tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in t.parameters.items())
            tool_descs.append(f"  - {t.name}({params}): {t.description}")
        tool_section = "\n".join(tool_descs)

        format_block = REACT_FORMAT_INSTRUCTION.replace("{tool_descriptions}", tool_section)

        ctx_lines = "\n".join(f"  {k}: {v}" for k, v in context.items())

        # Scratchpad — only show non-error steps to keep context clean
        pad_lines = []
        for s in scratchpad:
            if s.type == StepType.THOUGHT:
                pad_lines.append(f"[Thought] {s.content}")
            elif s.type == StepType.ACTION:
                pad_lines.append(f"[Action] {s.tool_name}({json.dumps(s.tool_args, ensure_ascii=False)})")
            elif s.type == StepType.OBSERVATION:
                obs = s.content[:3000] + ("..." if len(s.content) > 3000 else "")
                pad_lines.append(f"[Observation] {obs}")
            elif s.type == StepType.ERROR and "Rate limited" not in s.content:
                pad_lines.append(f"[Error] {s.content[:200]}")
            elif s.type == StepType.FINAL:
                pad_lines.append(f"[Final] {s.content}")

        scratchpad_text = "\n".join(pad_lines) if pad_lines else "(none yet)"

        return f"""{format_block}

TASK:
{task}

CONTEXT:
{ctx_lines}

SCRATCHPAD (your work so far):
{scratchpad_text}

Now decide your next action. Respond with JSON only."""

    # ── Private: Force Final Answer ──────────────────────────────────────────

    def _force_final_answer(self, task: str, scratchpad: List[Step], context: Dict) -> str:
        """When max steps reached, ask the LLM to summarize what was done."""
        observations = [s.content for s in scratchpad if s.type == StepType.OBSERVATION]
        summary_input = "\n".join(observations[:10])

        ai = get_ai_provider()
        return ai.chat(
            "Summarize the work done so far. List all RFIs and Risks created. Be concise.",
            f"Task: {task}\n\nObservations:\n{summary_input[:5000]}",
        )

    # ── Private: Fallback Summary ────────────────────────────────────────────

    @staticmethod
    def _build_fallback_summary(steps: List[Step], artifacts: List[Dict]) -> str:
        """Build a summary from artifacts when the LLM call fails."""
        rfi_count = sum(1 for a in artifacts if a.get("type") == "rfi")
        risk_count = sum(1 for a in artifacts if a.get("type") == "risk")

        summary = f"Agent completed analysis. Created {rfi_count} RFIs and {risk_count} Risks.\n\n"
        if artifacts:
            summary += "Artifacts created:\n"
            for a in artifacts:
                summary += f"  - {a.get('type', '?').upper()} #{a.get('id')}: {a.get('title', 'N/A')}"
                if a.get("severity"):
                    summary += f" [{a['severity']}]"
                summary += "\n"
        return summary

    # ── Private: Artifact Extraction ─────────────────────────────────────────

    @staticmethod
    def _extract_artifacts(observation: str, artifacts: List[Dict]):
        """Parse structured artifact references from tool output."""
        rfi_match = re.search(r"RFI #(\d+) created: (.+)", observation)
        if rfi_match:
            artifacts.append({
                "type": "rfi",
                "id": int(rfi_match.group(1)),
                "title": rfi_match.group(2).strip(),
            })

        risk_match = re.search(r"Risk #(\d+) created: (.+?) \[(\w+)\]", observation)
        if risk_match:
            artifacts.append({
                "type": "risk",
                "id": int(risk_match.group(1)),
                "title": risk_match.group(2).strip(),
                "severity": risk_match.group(3),
            })

    # ── Private: Extract Retry Delay ─────────────────────────────────────────

    @staticmethod
    def _extract_retry_delay(error_msg: str) -> int:
        """Parse retry delay from rate limit error. Default 15s."""
        match = re.search(r"retry in (\d+)", error_msg.lower())
        if match:
            delay = int(match.group(1))
            return min(delay, 60)  # Cap at 60s
        return 15

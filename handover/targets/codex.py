"""
handover/targets/codex.py

Target adapter for OpenAI Codex CLI: generates AGENTS.md and TASKS.md.

AGENTS.md — project context: goal, tech stack, constraints, open questions.
TASKS.md  — implementation task list with status checkboxes.

These are product conventions defined by handover; AGENTS.md aligns with the
filename used by the Codex CLI for agent instructions.

Phase 5 — Multi-Target Agents.
Phase 6 — Agent-Aware Output (TASKS.md added).
"""

from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext
from handover.targets.base import BaseTarget

_AGENTS_FILENAME = "AGENTS.md"
_TASKS_FILENAME = "TASKS.md"


class CodexTarget(BaseTarget):
    """Generates AGENTS.md and TASKS.md for OpenAI Codex CLI."""

    @property
    def name(self) -> str:
        """Target identifier: 'codex'."""
        return "codex"

    def describe(self) -> dict[str, str]:
        """Return human-readable metadata about this target."""
        return {
            "name": "codex",
            "description": "OpenAI Codex CLI — generates AGENTS.md (context) and TASKS.md (task list)",
        }

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate AGENTS.md and TASKS.md from the HandoverContext.

        Args:
            context: Populated HandoverContext.
            output_dir: Directory to write the output files.
            dry_run: If True, return expected paths without writing.

        Returns:
            [output_dir/AGENTS.md, output_dir/TASKS.md]
        """
        agents_path = output_dir / _AGENTS_FILENAME
        tasks_path = output_dir / _TASKS_FILENAME
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            agents_path.write_text(self._render_agents(context), encoding="utf-8")
            tasks_path.write_text(self._render_tasks(context), encoding="utf-8")
        return [agents_path, tasks_path]

    def _render_agents(self, context: HandoverContext) -> str:
        """Render AGENTS.md — project context for Codex CLI."""
        lines: list[str] = ["# Agent Instructions", ""]

        lines += ["## Goal", context.goal or "(none)", ""]

        if context.tech_stack:
            lines.append("## Tech Stack")
            for key, value in context.tech_stack.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        if context.decisions:
            lines.append("## Key Decisions")
            for decision in context.decisions:
                entry = f"- **{decision.topic}**: {decision.decision}"
                if decision.rationale:
                    entry += f" _{decision.rationale}_"
                lines.append(entry)
            lines.append("")

        if context.constraints:
            lines.append("## Constraints")
            for constraint in context.constraints:
                lines.append(f"- {constraint}")
            lines.append("")

        if context.open_questions:
            lines.append("## Open Questions")
            for question in context.open_questions:
                lines.append(f"- {question}")
            lines.append("")

        return "\n".join(lines)

    def _render_tasks(self, context: HandoverContext) -> str:
        """Render TASKS.md — implementation task list for Codex CLI."""
        lines: list[str] = ["# Tasks", ""]

        if context.tasks:
            for i, task in enumerate(context.tasks, 1):
                status = "[x]" if task.done else "[ ]"
                priority = f" _(high priority)_" if task.priority == "high" else ""
                lines.append(f"{i}. {status} {task.title}{priority}")
                if task.description:
                    lines.append(f"   {task.description}")
            lines.append("")
        else:
            lines += ["_(No tasks extracted from conversation.)_", ""]

        return "\n".join(lines)

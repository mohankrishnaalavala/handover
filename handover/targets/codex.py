"""
handover/targets/codex.py

Target adapter for OpenAI Codex CLI: generates AGENTS.md.

Format:
  # Agent Instructions
  ## Goal
  ## Tech Stack
  ## Tasks
  ## Constraints
  ## Open Questions

Phase 5 — Multi-Target Agents.
"""

from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext
from handover.targets.base import BaseTarget

_OUTPUT_FILENAME = "AGENTS.md"


class CodexTarget(BaseTarget):
    """Generates AGENTS.md for OpenAI Codex CLI."""

    @property
    def name(self) -> str:
        """Target identifier: 'codex'."""
        return "codex"

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate AGENTS.md from the HandoverContext.

        Args:
            context: Populated HandoverContext.
            output_dir: Directory to write the output file.
            dry_run: If True, return expected path without writing.

        Returns:
            [output_dir/AGENTS.md]
        """
        output_path = output_dir / _OUTPUT_FILENAME
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(self._render(context), encoding="utf-8")
        return [output_path]

    def _render(self, context: HandoverContext) -> str:
        """Render the AGENTS.md content from context."""
        lines: list[str] = ["# Agent Instructions", ""]

        lines += ["## Goal", context.goal or "(none)", ""]

        if context.tech_stack:
            lines.append("## Tech Stack")
            for key, value in context.tech_stack.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        if context.tasks:
            lines.append("## Tasks")
            for i, task in enumerate(context.tasks, 1):
                status = "[x]" if task.done else "[ ]"
                lines.append(f"{i}. {status} {task.title}")
                if task.description:
                    lines.append(f"   {task.description}")
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

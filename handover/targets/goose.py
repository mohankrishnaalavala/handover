"""
handover/targets/goose.py

Target adapter for Block's Goose: generates goose-context.json.

Format:
  {
    "goal": "...",
    "tech_stack": {},
    "tasks": [{"title": "...", "priority": "high", "done": false}],
    "constraints": [],
    "open_questions": []
  }

Phase 5 — Multi-Target Agents.
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.models import HandoverContext
from handover.targets.base import BaseTarget

_OUTPUT_FILENAME = "goose-context.json"


class GooseTarget(BaseTarget):
    """Generates goose-context.json for Block's Goose."""

    @property
    def name(self) -> str:
        """Target identifier: 'goose'."""
        return "goose"

    def describe(self) -> dict[str, str]:
        """Return human-readable metadata about this target."""
        return {
            "name": "goose",
            "description": "Goose (Block) — generates goose-context.json",
        }

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate goose-context.json from the HandoverContext.

        Args:
            context: Populated HandoverContext.
            output_dir: Directory to write the output file.
            dry_run: If True, return expected path without writing.

        Returns:
            [output_dir/goose-context.json]
        """
        output_path = output_dir / _OUTPUT_FILENAME
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(self._render(context), encoding="utf-8")
        return [output_path]

    def _render(self, context: HandoverContext) -> str:
        """Render the goose-context.json content from context."""
        data = {
            "goal": context.goal,
            "tech_stack": context.tech_stack,
            "tasks": [
                {
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "done": task.done,
                }
                for task in context.tasks
            ],
            "constraints": context.constraints,
            "open_questions": context.open_questions,
        }
        return json.dumps(data, indent=2) + "\n"

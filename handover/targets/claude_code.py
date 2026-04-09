"""
handover/targets/claude_code.py

Target adapter for Claude Code: generates CLAUDE.md + PLAN.md.

Delegates to the existing Generator so Jinja2 template logic is not duplicated.
Supports custom template directories via the constructor.

Phase 5 — Multi-Target Agents.
"""

from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext
from handover.targets.base import BaseTarget


class ClaudeCodeTarget(BaseTarget):
    """Generates CLAUDE.md and PLAN.md for Claude Code."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """
        Initialize the ClaudeCodeTarget.

        Args:
            template_dir: Optional path to a custom Jinja2 templates directory.
                          Passed through to Generator; defaults to bundled templates.
        """
        self._template_dir = template_dir

    @property
    def name(self) -> str:
        """Target identifier: 'claude-code'."""
        return "claude-code"

    def describe(self) -> dict[str, str]:
        """Return human-readable metadata about this target."""
        return {
            "name": "claude-code",
            "description": "Claude Code — generates CLAUDE.md + PLAN.md",
        }

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate CLAUDE.md and PLAN.md via the Generator.

        Args:
            context: Populated HandoverContext.
            output_dir: Directory to write the output files.
            dry_run: If True, return expected paths without writing files.

        Returns:
            List of Paths: [output_dir/CLAUDE.md, output_dir/PLAN.md].
        """
        from handover.generator import Generator

        result = Generator(template_dir=self._template_dir).generate(
            context, output_dir, dry_run=dry_run
        )
        return [output_dir / filename for filename in result]

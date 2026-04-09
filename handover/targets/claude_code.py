"""
handover/targets/claude_code.py

Target adapter for Claude Code: generates CLAUDE.md + PLAN.md and (when the
two-layer scaffold is on) the `.claude/` workspace as well.

Phase 5 — Multi-Target Agents.
v1.1.0 — Two-Layer Scaffold (CLAUDE.md becomes a thin index, `.claude/` is
generated from a `ScaffoldContext`).
"""

from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext, ScaffoldContext
from handover.targets.base import BaseTarget


class ClaudeCodeTarget(BaseTarget):
    """Generates CLAUDE.md, PLAN.md, and optionally the `.claude/` workspace."""

    def __init__(
        self,
        template_dir: Path | None = None,
        *,
        scaffold: ScaffoldContext | None = None,
        overwrite_workspace: bool = False,
    ) -> None:
        """
        Initialize the ClaudeCodeTarget.

        Args:
            template_dir: Optional path to a custom Jinja2 templates directory.
                          Passed through to Generator; defaults to bundled templates.
            scaffold: When provided, the target writes a thin CLAUDE.md index
                      and generates the `.claude/` workspace from it. When
                      None, the legacy single-layer behaviour is used.
            overwrite_workspace: Allow `.claude/` to be replaced if it
                      already exists. Mirrors the `--overwrite-handover-dir`
                      flag.
        """
        self._template_dir = template_dir
        self._scaffold = scaffold
        self._overwrite_workspace = overwrite_workspace

    @property
    def name(self) -> str:
        """Target identifier: 'claude-code'."""
        return "claude-code"

    def describe(self) -> dict[str, str]:
        """Return human-readable metadata about this target."""
        return {
            "name": "claude-code",
            "description": (
                "Claude Code — generates CLAUDE.md + PLAN.md, plus a "
                "`.claude/` workspace when the two-layer scaffold is on."
            ),
        }

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate CLAUDE.md, PLAN.md, and optionally `.claude/`.

        Args:
            context: Populated HandoverContext.
            output_dir: Directory to write the output files.
            dry_run: If True, return expected paths without writing files.

        Returns:
            List of Paths produced. Always includes CLAUDE.md and PLAN.md.
            When the two-layer scaffold is on, also includes every file
            under `output_dir/.claude/`.
        """
        from handover.generator import Generator

        gen = Generator(template_dir=self._template_dir)
        written: list[Path] = []

        if self._scaffold is None:
            # Legacy single-layer behaviour — unchanged from v1.0.x.
            result = gen.generate(context, output_dir, dry_run=dry_run)
            written.extend(output_dir / filename for filename in result)
            return written

        # Two-layer mode: thin CLAUDE.md indexing into `.handover/`,
        # plus the `.claude/` workspace from the ScaffoldContext.
        claude_md = gen.render_claude_md_v2(context)
        plan_md = gen.render_plan_md(context)

        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
            (output_dir / "PLAN.md").write_text(plan_md, encoding="utf-8")
        written.append(output_dir / "CLAUDE.md")
        written.append(output_dir / "PLAN.md")

        from handover.scaffold_generator import generate_claude_workspace

        workspace_paths = generate_claude_workspace(
            self._scaffold,
            output_dir,
            overwrite=self._overwrite_workspace,
            dry_run=dry_run,
        )
        written.extend(workspace_paths)
        return written

"""
handover/generator.py

Generator component: produces CLAUDE.md and PLAN.md from a HandoverContext.
See PRD Section 6 — Architecture (Generator component).
See PRD Section 10 — Output Artifacts.

Uses Jinja2 templates. Default templates are in handover/templates/.
Custom templates can be provided via --template flag or handover init.
"""

from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext

# TODO: implement — see PRD Section 6 and PRD Section 10

DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"


class Generator:
    """
    Generate CLAUDE.md and PLAN.md from a HandoverContext using Jinja2 templates.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """
        Initialize the Generator.

        Args:
            template_dir: Path to a directory containing claude_md.j2 and plan_md.j2.
                          Defaults to handover/templates/ (bundled defaults).
        """
        self.template_dir = template_dir or DEFAULT_TEMPLATE_DIR
        # TODO: implement — load Jinja2 environment from template_dir

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """
        Generate CLAUDE.md and PLAN.md from the given HandoverContext.

        Args:
            context: Populated HandoverContext from the Summarizer.
            output_dir: Directory to write output files.
            dry_run: If True, return rendered content without writing files.

        Returns:
            Dict mapping filename to rendered content:
            {"CLAUDE.md": "...", "PLAN.md": "..."}
        """
        # TODO: implement
        raise NotImplementedError

    def render_claude_md(self, context: HandoverContext) -> str:
        """
        Render the CLAUDE.md artifact.

        Args:
            context: Populated HandoverContext.

        Returns:
            Rendered CLAUDE.md as a string.
        """
        # TODO: implement — render claude_md.j2 with context
        raise NotImplementedError

    def render_plan_md(self, context: HandoverContext) -> str:
        """
        Render the PLAN.md artifact.

        Args:
            context: Populated HandoverContext.

        Returns:
            Rendered PLAN.md as a string.
        """
        # TODO: implement — render plan_md.j2 with context
        raise NotImplementedError

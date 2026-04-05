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

from jinja2 import Environment, FileSystemLoader, select_autoescape

from handover import __version__
from handover.models import HandoverContext

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
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape([]),  # Markdown output — no HTML escaping
            trim_blocks=True,
            lstrip_blocks=True,
        )

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
        claude_md = self.render_claude_md(context)
        plan_md = self.render_plan_md(context)
        result = {"CLAUDE.md": claude_md, "PLAN.md": plan_md}

        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
            (output_dir / "PLAN.md").write_text(plan_md, encoding="utf-8")

        return result

    def render_claude_md(self, context: HandoverContext) -> str:
        """
        Render the CLAUDE.md artifact.

        Args:
            context: Populated HandoverContext.

        Returns:
            Rendered CLAUDE.md as a string.
        """
        template = self._env.get_template("claude_md.j2")
        return str(template.render(context=context, version=__version__))

    def render_plan_md(self, context: HandoverContext) -> str:
        """
        Render the PLAN.md artifact.

        Args:
            context: Populated HandoverContext.

        Returns:
            Rendered PLAN.md as a string.
        """
        template = self._env.get_template("plan_md.j2")
        return str(template.render(context=context, version=__version__))

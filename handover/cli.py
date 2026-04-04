"""
handover/cli.py

Click CLI entry point for the handover tool.
See PRD Section 11 — CLI Interface.

Subcommands:
  handover (main)  — parse export, generate CLAUDE.md + PLAN.md
  handover list    — enumerate conversations in a bulk JSONL export
  handover init    — scaffold custom templates to ~/.handover/templates/
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from handover import __version__

# TODO: implement — see PRD Section 11


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--input", "-i", "input_file", type=click.Path(exists=True), required=False,
              help="Path to the chat export file (.json, .jsonl, .md)")
@click.option("--output", "-o", "output_dir", type=click.Path(), required=False,
              help="Directory to write CLAUDE.md and PLAN.md")
@click.option("--source", type=click.Choice(["claude"]), default=None,
              help="Force a specific parser adapter (default: auto-detect)")
@click.option("--title", default=None,
              help="Select conversation by title from a bulk JSONL export")
@click.option("--id", "conversation_id", default=None,
              help="Select conversation by ID from a bulk JSONL export")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print what would be written without writing files")
@click.option("--no-llm", is_flag=True, default=False,
              help="Use rule-based extraction only (no API key required)")
@click.option("--launch", is_flag=True, default=False,
              help="Run `claude` in the output directory after writing files")
@click.option("--template", type=click.Path(), default=None,
              help="Path to custom Jinja2 templates directory")
@click.version_option(version=__version__, prog_name="handover")
def main(
    ctx: click.Context,
    input_file: str | None,
    output_dir: str | None,
    source: str | None,
    title: str | None,
    conversation_id: str | None,
    dry_run: bool,
    no_llm: bool,
    launch: bool,
    template: str | None,
) -> None:
    """
    handover — Universal AI Chat to Local Agent Handover Tool.

    Design in chat. Build in terminal. Zero context lost.

    Parse a Claude chat export and generate CLAUDE.md + PLAN.md for
    immediate use with Claude Code or another terminal agent.

    Examples:

      handover --input chat.json --output ./my-project/

      handover --input export.jsonl --title "API Design" --output ./my-project/

      handover --input chat.json --dry-run
    """
    if ctx.invoked_subcommand is not None:
        return

    # TODO: implement main command logic
    # 1. Validate --input and --output are provided
    # 2. Detect or use explicit --source to get the right parser
    # 3. Parse the file (and filter by --title/--id if bulk JSONL)
    # 4. Summarize (LLM or heuristics based on --no-llm)
    # 5. Generate artifacts (respect --dry-run and --template)
    # 6. If --launch, exec `claude` in output_dir

    if not input_file:
        click.echo("Error: --input is required.", err=True)
        sys.exit(1)
    if not output_dir:
        click.echo("Error: --output is required.", err=True)
        sys.exit(1)

    click.echo("handover: not yet implemented — see PLAN.md for implementation tasks")


@main.command("list")
@click.argument("export_file", type=click.Path(exists=True))
def list_conversations(export_file: str) -> None:
    """
    List all conversations in a bulk JSONL export.

    EXPORT_FILE: Path to the bulk .jsonl export from Claude Settings → Privacy → Export Data.

    Example:

      handover list export.jsonl
    """
    # TODO: implement
    # 1. Use ClaudeParser.list_conversations(export_file)
    # 2. Print table: ID | DATE | TITLE
    click.echo("handover list: not yet implemented — see PLAN.md")


@main.command("init")
def init_templates() -> None:
    """
    Scaffold customizable Jinja2 templates to ~/.handover/templates/.

    After running, edit:
      ~/.handover/templates/claude_md.j2
      ~/.handover/templates/plan_md.j2

    Then use --template ~/.handover/templates/ on any handover run.
    """
    # TODO: implement
    # 1. Create ~/.handover/templates/
    # 2. Copy bundled templates from handover/templates/
    # 3. Print confirmation and next steps
    click.echo("handover init: not yet implemented — see PLAN.md")

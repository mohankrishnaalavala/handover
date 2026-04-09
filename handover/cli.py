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

import shutil
import subprocess
from pathlib import Path

import click

from handover import __version__
from handover.targets import list_targets

# Build valid --target choices dynamically from the registry so that
# newly registered targets are automatically accepted without editing cli.py.
_TARGET_CHOICES: list[str] = list_targets() + ["all"]


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--input",
    "-i",
    "input_file",
    type=click.Path(exists=True),
    required=False,
    help="Path to the chat export file (.json, .jsonl, .md)",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    required=False,
    help="Directory to write CLAUDE.md and PLAN.md",
)
@click.option(
    "--source",
    type=click.Choice(["claude", "chatgpt", "gemini", "perplexity"]),
    default=None,
    help="Force a specific parser adapter (default: auto-detect)",
)
@click.option(
    "--title",
    default=None,
    help="Select conversation by title from a bulk JSONL export",
)
@click.option(
    "--id",
    "conversation_id",
    default=None,
    help="Select conversation by ID from a bulk JSONL export",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing files",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Use rule-based extraction only (no API key required)",
)
@click.option(
    "--launch",
    is_flag=True,
    default=False,
    help="Run `claude` in the output directory after writing files",
)
@click.option(
    "--template",
    type=click.Path(),
    default=None,
    help="Path to custom Jinja2 templates directory (claude-code target only)",
)
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default="claude-code",
    show_default=True,
    help="Output target (coding agent). 'all' writes every registered format.",
)
@click.option(
    "--publish",
    is_flag=True,
    default=False,
    help="Publish generated artifacts to a GitHub Gist after writing (requires gh CLI).",
)
@click.option(
    "--no-handover-dir",
    is_flag=True,
    default=False,
    help="Skip the .handover/ knowledge base (legacy v1.0.x output only).",
)
@click.option(
    "--handover-dir-only",
    is_flag=True,
    default=False,
    help="Generate the .handover/ knowledge base but skip target-specific files.",
)
@click.option(
    "--overwrite-handover-dir",
    is_flag=True,
    default=False,
    help="Replace an existing .handover/ (and .claude/) directory.",
)
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
    target: str,
    publish: bool,
    no_handover_dir: bool,
    handover_dir_only: bool,
    overwrite_handover_dir: bool,
) -> None:
    """
    handover — Universal AI Chat to Local Agent Handover Tool.

    Design in chat. Build in terminal. Zero context lost.

    Parse a chat export and generate agent-specific context files for your local
    coding agent. Each target produces the file(s) that agent expects:
    Claude Code (CLAUDE.md + PLAN.md), Codex (AGENTS.md + TASKS.md),
    Copilot (.github/copilot-instructions.md), aider, Goose, and more.

    Examples:

      handover --input chat.json --output ./my-project/

      handover --input chat.json --output ./my-project/ --target codex

      handover --input chat.json --output ./my-project/ --target copilot

      handover --input export.jsonl --title "API Design" --output ./my-project/

      handover --input chat.json --output ./my-project/ --target all --dry-run
    """
    if ctx.invoked_subcommand is not None:
        return

    # Validate required flags
    if not input_file:
        raise click.UsageError("--input is required.")
    if not output_dir:
        raise click.UsageError("--output is required.")

    from handover.models import HandoverAPIError
    from handover.parsers import detect_source, get_parser

    input_path = Path(input_file)
    output_path = Path(output_dir)

    # Auto-detect source adapter
    if source is None:
        try:
            source = detect_source(str(input_path))
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    parser = get_parser(source)

    # Parse the file — generalized conversation filter via BaseParser.parse_by_id()
    messages = None
    selected_conv: dict[str, str] | None = None
    try:
        if title or conversation_id:
            conversations = parser.list_conversations(input_path)
            selected_conv = next(
                (
                    c
                    for c in conversations
                    if (title and title.strip().lower() in c["title"].strip().lower())
                    or (conversation_id and c["id"] == conversation_id)
                ),
                None,
            )
            if selected_conv is None:
                hint = f"title={title!r} (substring match)" if title else f"id={conversation_id!r}"
                raise click.ClickException(
                    f"No conversation found with {hint}. "
                    "Run `handover list <export_file>` to see available conversations."
                )
            messages = parser.parse_by_id(input_path, selected_conv["id"])
        else:
            messages = parser.parse(input_path)
    except click.ClickException:
        raise
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    if not messages:
        raise click.ClickException("No messages found in the export file.")

    # Summarize
    from handover import summarizer

    try:
        context = summarizer.summarize(messages, use_llm=not no_llm)
    except HandoverAPIError as e:
        raise click.ClickException(str(e)) from e

    # Populate metadata not set by summarizer
    context.source = source
    fmt_version = parser.detect_format_version(input_path)
    context.source_version = fmt_version

    # Populate conversation title/id from file metadata if not set by summarizer
    if not context.conversation_title:
        if selected_conv:
            # We already have the target conversation's metadata
            context.conversation_title = selected_conv.get("title", "")
            context.conversation_id = selected_conv.get("id")
        elif source == "claude":
            try:
                import json as _json

                if input_path.suffix.lower() == ".json":
                    data = _json.loads(input_path.read_text(encoding="utf-8"))
                    # JSON array — use first conversation
                    if isinstance(data, list) and data:
                        context.conversation_title = data[0].get("name", "")
                        context.conversation_id = data[0].get("uuid")
                    elif isinstance(data, dict):
                        context.conversation_title = data.get("name", "")
                        context.conversation_id = data.get("uuid")
            except Exception:
                pass

    # v1.1.0 — Two-Layer Scaffold extraction.
    # When --no-handover-dir is NOT set, build a ScaffoldContext that powers
    # both the universal `.handover/` knowledge base and the per-target
    # `.claude/` workspace. Costs exactly one extra Claude API call (or
    # zero with --no-llm).
    if no_handover_dir and handover_dir_only:
        raise click.UsageError("--no-handover-dir and --handover-dir-only are mutually exclusive.")

    scaffold = None
    if not no_handover_dir:
        from handover.scaffold_extractor import extract_scaffold

        try:
            scaffold = extract_scaffold(
                messages,
                context,
                use_llm=not no_llm,
                target=target,
            )
        except HandoverAPIError as e:
            raise click.ClickException(str(e)) from e

    # Generate artifacts
    from handover.targets import get_target, list_targets
    from handover.targets.base import BaseTarget
    from handover.targets.claude_code import ClaudeCodeTarget

    template_dir = Path(template) if template else None
    targets_to_run: list[str] = list_targets() if target == "all" else [target]

    def _make_target(t_name: str) -> BaseTarget:
        """Instantiate a target, applying template_dir to ClaudeCodeTarget."""
        if t_name == "claude-code":
            return ClaudeCodeTarget(
                template_dir=template_dir,
                scaffold=scaffold,
                overwrite_workspace=overwrite_handover_dir,
            )
        return get_target(t_name)

    if dry_run:
        from handover.universal_generator import write_handover_dir

        click.echo(f"\nParsing: {context.conversation_title or input_path.name!r}")
        click.echo(f"  Source : {source} ({fmt_version})")
        click.echo(f"  Messages: {len(messages)}")
        click.echo("\nExtracted:")
        click.echo(f"  Goal       : {context.goal or '(none detected)'}")
        click.echo(f"  Tech Stack : {', '.join(context.tech_stack.values()) or '(none detected)'}")
        click.echo(f"  Decisions  : {len(context.decisions)}")
        click.echo(f"  Tasks      : {len(context.tasks)}")
        click.echo(f"  Constraints: {len(context.constraints)}")
        click.echo(f"  Questions  : {len(context.open_questions)}")

        layers = []
        if scaffold is not None:
            layers.append(".handover/")
        if not handover_dir_only:
            layers.append(f"target={target}")
        click.echo(f"\nLayers: {', '.join(layers) or '(none)'}")
        click.echo(f"Would write to {output_path}/:")

        if scaffold is not None:
            for p in write_handover_dir(scaffold, output_path, dry_run=True):
                click.echo(f"  -> {p.relative_to(output_path)}")
        if not handover_dir_only:
            for t_name in targets_to_run:
                paths = _make_target(t_name).generate(context, output_path, dry_run=True)
                for p in paths:
                    click.echo(f"  -> {p.relative_to(output_path)}")
        click.echo("\nRun without --dry-run to write files.")
    else:
        from handover.universal_generator import HandoverDirExistsError, write_handover_dir

        all_paths: list[Path] = []
        if scaffold is not None:
            try:
                all_paths.extend(
                    write_handover_dir(
                        scaffold,
                        output_path,
                        overwrite=overwrite_handover_dir,
                    )
                )
            except HandoverDirExistsError as e:
                raise click.ClickException(str(e)) from e
        if not handover_dir_only:
            for t_name in targets_to_run:
                all_paths.extend(_make_target(t_name).generate(context, output_path, dry_run=False))
        names = ", ".join(str(p.relative_to(output_path)) for p in all_paths)
        click.echo(f"Wrote {names} to {output_path}/")

        # Record to history
        from handover.history import make_id, now_iso, record
        from handover.models import HistoryEntry

        entry = HistoryEntry(
            handover_id=make_id(),
            timestamp=now_iso(),
            source=source,
            conversation_title=context.conversation_title,
            input_file=str(input_path.resolve()),
            output_dir=str(output_path.resolve()),
            artifacts=[p.name for p in all_paths],
            target=target,
            use_llm=not no_llm,
        )
        record(entry)
        click.echo(f"History: {entry.handover_id}")

        # --publish: create a GitHub Gist
        if publish:
            from handover.publisher import PublisherError
            from handover.publisher import publish as _publish

            file_contents = {
                p.name: p.read_text(encoding="utf-8")
                for p in all_paths
                if p.suffix in {".md", ".yml", ".yaml", ".json"}
            }
            desc = f"handover: {context.conversation_title or input_path.name}"
            try:
                gist_url = _publish(file_contents, description=desc)
                click.echo(f"Published  → {gist_url}")
                click.echo(f"Pull later : handover pull {gist_url}")
            except PublisherError as e:
                click.echo(f"Warning: publish failed — {e}", err=True)

    # --launch: open claude in output directory
    if launch and not dry_run:
        try:
            subprocess.run(["claude"], cwd=str(output_path), check=False)
        except FileNotFoundError:
            click.echo(
                "Warning: `claude` command not found. Install Claude Code: https://claude.ai/code",
                err=True,
            )


@main.command("list")
@click.argument("export_file", type=click.Path(exists=True))
@click.option(
    "--source",
    type=click.Choice(["claude", "chatgpt", "gemini", "perplexity"]),
    default=None,
    help="Force a specific parser adapter (default: auto-detect)",
)
def list_conversations(export_file: str, source: str | None) -> None:
    """
    List all conversations in a multi-conversation export file.

    EXPORT_FILE: Path to the export file (e.g. bulk .jsonl, conversations.json).

    Example:

      handover list export.jsonl
      handover list conversations.json
    """
    from handover.parsers import detect_source, get_parser

    export_path = Path(export_file)
    if source is None:
        try:
            source = detect_source(str(export_path))
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    parser = get_parser(source)
    try:
        conversations = parser.list_conversations(export_path)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    if not conversations:
        click.echo("No conversations found.")
        return

    # Table header
    click.echo(f"\n{'ID':<38}  {'DATE':<12}  TITLE")
    click.echo("-" * 100)
    for conv in conversations:
        date = conv["date"][:10] if conv["date"] else "unknown   "
        click.echo(f"{conv['id']:<38}  {date:<12}  {conv['title']}")
    click.echo(f"\n{len(conversations)} conversation(s) found.")


@main.command("serve")
@click.option("--port", default=7437, show_default=True, help="Port to listen on (7437 = H-A-N-D)")
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    default=None,
    help="Directory where CLAUDE.md + PLAN.md are written (default: cwd)",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Use rule-based extraction only (no API key required)",
)
@click.option(
    "--daemon",
    is_flag=True,
    default=False,
    help="Run as a background process and return immediately",
)
def serve(port: int, output_dir: str | None, no_llm: bool, daemon: bool) -> None:
    """
    Start the local HTTP bridge for the browser extension.

    The server listens for POST /handover requests from the Chrome/Firefox
    extension and runs the full pipeline, writing CLAUDE.md and PLAN.md to
    the configured output directory.

    Endpoints:
      GET  /health   — liveness check
      POST /handover — run pipeline from raw conversation JSON
      POST /config   — update output_dir / no_llm at runtime

    Examples:

      handover serve

      handover serve --port 7437 --output ~/projects/myapp/

      handover serve --no-llm --daemon
    """
    import subprocess as _subprocess
    import sys

    resolved_output = output_dir or str(Path.cwd())

    if daemon:
        log_path = Path.home() / ".handover" / "server.log"
        pid_path = Path.home() / ".handover" / "server.pid"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "handover",
            "serve",
            "--port",
            str(port),
            "--output",
            resolved_output,
        ]
        if no_llm:
            cmd.append("--no-llm")

        with log_path.open("w") as log_file:
            proc = _subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )

        pid_path.write_text(str(proc.pid))
        click.echo(f"handover serve started  PID {proc.pid}  http://localhost:{port}")
        click.echo(f"Log: {log_path}")
        return

    from handover.server import run_server

    run_server(port=port, output_dir=resolved_output, no_llm=no_llm)


@main.command("init")
def init_templates() -> None:
    """
    Scaffold customizable Jinja2 templates to ~/.handover/templates/.

    After running, edit:
      ~/.handover/templates/claude_md.j2
      ~/.handover/templates/plan_md.j2

    Then use --template ~/.handover/templates/ on any handover run.
    """
    template_src = Path(__file__).parent / "templates"
    template_dst = Path.home() / ".handover" / "templates"
    template_dst.mkdir(parents=True, exist_ok=True)

    for template_file in sorted(template_src.glob("*.j2")):
        dst = template_dst / template_file.name
        shutil.copy2(template_file, dst)
        click.echo(f"  Copied {template_file.name} -> {dst}")

    click.echo(f"\nTemplates scaffolded to {template_dst}")
    click.echo("Edit them, then use: handover --template ~/.handover/templates/ ...")


# ---------------------------------------------------------------------------
# Phase 4 — Reverse handover
# ---------------------------------------------------------------------------


@main.command("reverse")
@click.option(
    "--session",
    "session_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to a specific Claude Code session .jsonl file",
)
@click.option(
    "--project",
    "-p",
    "project_dir",
    type=click.Path(),
    default=None,
    help="Project root directory (auto-discovers most recent session)",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    default=None,
    help="Directory to write HANDOVER.md (default: project dir or cwd)",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Use heuristic extraction only (no API key required)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing files",
)
def reverse_handover(
    session_file: str | None,
    project_dir: str | None,
    output_dir: str | None,
    no_llm: bool,
    dry_run: bool,
) -> None:
    """
    Generate HANDOVER.md from a Claude Code session log.

    Reads ~/.claude/projects/<hash>/<session>.jsonl, extracts files changed,
    decisions made, tasks completed, and recommended next steps.

    Examples:

      handover reverse --project .

      handover reverse --session ~/.claude/projects/abc/session.jsonl

      handover reverse --project . --no-llm --dry-run
    """
    from handover.generator import Generator
    from handover.models import HandoverAPIError
    from handover.parsers.claude_code import ClaudeCodeSessionParser
    from handover.reverse import reverse

    resolved_project = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()

    if session_file:
        resolved_session = Path(session_file)
    else:
        # Auto-discover most recent session for this project
        parser = ClaudeCodeSessionParser()
        sessions = parser.discover_sessions(resolved_project)
        if not sessions:
            raise click.ClickException(
                f"No Claude Code sessions found for {resolved_project}.\n"
                "Run a Claude Code session first, or provide --session explicitly."
            )
        resolved_session = sessions[0].file_path
        click.echo(f"Using most recent session: {resolved_session.name}")

    resolved_output = Path(output_dir) if output_dir else resolved_project

    try:
        context = reverse(
            session_file=resolved_session,
            project_dir=resolved_project,
            use_llm=not no_llm,
        )
    except HandoverAPIError as exc:
        raise click.ClickException(str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc

    gen = Generator()

    if dry_run:
        result = gen.generate_handover(context, resolved_output, dry_run=True)
        click.echo(f"\nSession: {context.session_id[:8]}  Branch: {context.git_branch}")
        click.echo(f"  Files changed : {len(context.files_changed)}")
        click.echo(f"  Commands run  : {len(context.commands_run)}")
        click.echo(f"  Decisions     : {len(context.decisions)}")
        click.echo(f"  Tasks done    : {len(context.tasks_completed)}")
        click.echo(f"  Tasks remaining: {len(context.tasks_remaining)}")
        click.echo(f"  Next steps    : {len(context.next_steps)}")
        click.echo(f"\nWould write to {resolved_output}/:")
        for filename, content in result.items():
            size_kb = len(content.encode()) / 1024
            click.echo(f"  -> {filename}  ({size_kb:.1f} KB)")
        click.echo("\nRun without --dry-run to write files.")
    else:
        gen.generate_handover(context, resolved_output, dry_run=False)
        click.echo(f"Wrote HANDOVER.md to {resolved_output}/")


@main.command("sessions")
@click.option(
    "--project",
    "-p",
    "project_dir",
    type=click.Path(),
    default=None,
    help="Project root directory (default: cwd)",
)
@click.option("--limit", default=10, show_default=True, help="Maximum sessions to list")
def list_sessions(project_dir: str | None, limit: int) -> None:
    """
    List recent Claude Code sessions for a project.

    Reads from ~/.claude/projects/<project-hash>/ and shows session metadata
    sorted by most recent first.

    Examples:

      handover sessions

      handover sessions --project ~/projects/myapp --limit 20
    """
    from handover.parsers.claude_code import ClaudeCodeSessionParser

    resolved = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    parser = ClaudeCodeSessionParser()
    sessions = parser.discover_sessions(resolved)

    if not sessions:
        click.echo(f"No Claude Code sessions found for {resolved}")
        click.echo(
            f"Expected: ~/.claude/projects/{ClaudeCodeSessionParser.project_hash(resolved)}/"
        )
        return

    click.echo(f"\nClaude Code sessions for {resolved.name}/\n")
    click.echo(f"{'SESSION ID':<38}  {'DATE':<12}  {'BRANCH':<24}  MSGS")
    click.echo("-" * 90)
    for s in sessions[:limit]:
        date = s.started_at[:10] if s.started_at else "unknown   "
        branch = (s.git_branch or "")[:24]
        click.echo(f"{s.session_id:<38}  {date:<12}  {branch:<24}  {s.message_count}")
    click.echo(f"\n{min(len(sessions), limit)} of {len(sessions)} session(s) shown.")


@main.command("watch")
@click.option(
    "--project",
    "-p",
    "project_dir",
    type=click.Path(),
    default=None,
    help="Project root directory to watch (default: cwd)",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    default=None,
    help="Directory to write HANDOVER.md (default: project dir)",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Use heuristic extraction only (no API key required)",
)
@click.option(
    "--idle",
    default=60,
    show_default=True,
    help="Seconds a session file must be idle before processing",
)
@click.option(
    "--daemon",
    is_flag=True,
    default=False,
    help="Run as a background process and return immediately",
)
def watch_sessions(
    project_dir: str | None,
    output_dir: str | None,
    no_llm: bool,
    idle: int,
    daemon: bool,
) -> None:
    """
    Watch for new Claude Code sessions and auto-generate HANDOVER.md.

    Monitors ~/.claude/projects/<hash>/ for new .jsonl files.  When a session
    file stops growing for --idle seconds it triggers the reverse pipeline
    automatically.

    Requires the optional 'watch' dependency:
      pip install handover[watch]

    Examples:

      handover watch --project .

      handover watch --project . --no-llm --daemon
    """
    import sys

    try:
        import watchdog  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "The 'watchdog' package is required for `handover watch`.\n"
            "Install it with:  pip install handover[watch]"
        ) from exc

    resolved_project = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    resolved_output = Path(output_dir).resolve() if output_dir else resolved_project

    if daemon:
        import subprocess as _subprocess

        log_path = Path.home() / ".handover" / "watch.log"
        pid_path = Path.home() / ".handover" / "watch.pid"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "handover",
            "watch",
            "--project",
            str(resolved_project),
            "--output",
            str(resolved_output),
            "--idle",
            str(idle),
        ]
        if no_llm:
            cmd.append("--no-llm")

        with log_path.open("w") as log_file:
            proc = _subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )

        pid_path.write_text(str(proc.pid))
        click.echo(f"handover watch started  PID {proc.pid}  project={resolved_project.name}")
        click.echo(f"Log: {log_path}")
        return

    from handover.watcher import start_watching

    click.echo(f"Watching Claude Code sessions for {resolved_project.name}/")
    click.echo(f"Output directory: {resolved_output}")
    click.echo(f"Idle threshold: {idle}s  |  LLM: {'off' if no_llm else 'on'}")
    click.echo("Press Ctrl-C to stop.\n")
    start_watching(
        project_dir=resolved_project,
        output_dir=resolved_output,
        no_llm=no_llm,
        idle_seconds=idle,
    )


# ---------------------------------------------------------------------------
# Phase 6 — Ecosystem & Developer Experience
# ---------------------------------------------------------------------------


@main.command("mcp")
def run_mcp_server() -> None:
    """
    Start the MCP server so Claude Code can call handover as a tool.

    Requires the optional [mcp] dependency:
      pip install handover[mcp]

    Add to ~/.claude/mcp.json:
      {
        "mcpServers": {
          "handover": {
            "command": "handover",
            "args": ["mcp"],
            "env": { "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}" }
          }
        }
      }

    Example:
      handover mcp
    """
    try:
        from handover.mcp_server import main as mcp_main
    except ImportError as exc:
        raise click.ClickException(
            "The 'mcp' package is required for `handover mcp`.\n"
            "Install it with:  pip install handover[mcp]"
        ) from exc

    mcp_main()


@main.command("history")
@click.option("--limit", default=20, show_default=True, help="Maximum entries to show")
@click.option(
    "--project",
    "-p",
    "project_dir",
    type=click.Path(),
    default=None,
    help="Filter to handovers whose output directory is inside this path",
)
def show_history(limit: int, project_dir: str | None) -> None:
    """
    List past handover runs from ~/.handover/history.jsonl.

    Examples:

      handover history

      handover history --limit 50

      handover history --project ~/projects/my-api/
    """
    from handover.history import HISTORY_PATH, load

    entries = load(limit=limit, output_dir=project_dir)
    if not entries:
        path_info = f" (file: {HISTORY_PATH})" if not HISTORY_PATH.exists() else ""
        click.echo(f"No handover history found{path_info}.")
        return

    click.echo(f"\n{'ID':<12}  {'DATE':<12}  {'SOURCE':<12}  {'TARGET':<14}  TITLE")
    click.echo("-" * 90)
    for e in entries:
        date = e.timestamp[:10]
        title = (e.conversation_title or e.input_file.split("/")[-1])[:40]
        click.echo(f"{e.handover_id:<12}  {date:<12}  {e.source:<12}  {e.target:<14}  {title}")
    click.echo(f"\n{len(entries)} entry(s) shown.")


@main.command("rerun")
@click.argument("handover_id")
def rerun_handover(handover_id: str) -> None:
    """
    Re-run a past handover by its ID.

    HANDOVER_ID: The ID shown by `handover history` (e.g. h_3f9a2c1b).

    Example:

      handover rerun h_3f9a2c1b
    """
    from handover.history import get_by_id

    entry = get_by_id(handover_id)
    if entry is None:
        raise click.ClickException(
            f"No history entry found for ID '{handover_id}'.\n"
            "Run `handover history` to list available entries."
        )

    click.echo(f"Re-running handover {handover_id}: {entry.input_file} → {entry.output_dir}")
    # Delegate to the main pipeline by invoking the main command programmatically
    from click.testing import CliRunner

    args = [
        "--input",
        entry.input_file,
        "--output",
        entry.output_dir,
        "--target",
        entry.target,
    ]
    if not entry.use_llm:
        args.append("--no-llm")

    runner = CliRunner()
    result = runner.invoke(main, args, catch_exceptions=False)
    click.echo(result.output)
    if result.exit_code != 0:
        raise click.ClickException("Re-run failed. See output above.")


@main.command("merge")
@click.option(
    "--input",
    "-i",
    "input_files",
    type=click.Path(exists=True),
    multiple=True,
    required=True,
    help="Chat export files to merge (pass multiple times)",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    required=True,
    help="Directory to write merged output files",
)
@click.option(
    "--source",
    type=click.Choice(["claude", "chatgpt", "gemini", "perplexity"]),
    default=None,
    help="Force a specific parser adapter for all inputs (default: auto-detect)",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Use heuristic merge instead of LLM synthesis",
)
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default="claude-code",
    show_default=True,
    help="Output target format",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing files",
)
def merge_command(
    input_files: tuple[str, ...],
    output_dir: str,
    source: str | None,
    no_llm: bool,
    target: str,
    dry_run: bool,
) -> None:
    """
    Merge multiple chat exports into one unified context.

    Useful when a design spans multiple separate chat sessions.

    Examples:

      handover merge --input session1.json --input session2.json --output ./project/

      handover merge --input s1.json --input s2.json --output . --no-llm
    """
    from handover.merger import merge_contexts
    from handover.models import HandoverAPIError
    from handover.parsers import detect_source, get_parser
    from handover.targets import get_target, list_targets
    from handover.targets.base import BaseTarget
    from handover.targets.claude_code import ClaudeCodeTarget

    if len(input_files) < 2:
        raise click.UsageError("--merge requires at least two --input files.")

    contexts = []
    for file_str in input_files:
        file_path = Path(file_str)
        src = source
        if src is None:
            try:
                src = detect_source(str(file_path))
            except ValueError as e:
                raise click.ClickException(str(e)) from e
        parser = get_parser(src)
        try:
            messages = parser.parse(file_path)
        except (ValueError, FileNotFoundError) as e:
            raise click.ClickException(f"Failed to parse {file_str}: {e}") from e
        if not messages:
            raise click.ClickException(f"No messages found in {file_str}.")

        from handover import summarizer as _sum

        try:
            ctx = _sum.summarize(messages, use_llm=not no_llm)
        except HandoverAPIError as e:
            raise click.ClickException(str(e)) from e
        ctx.source = src or "unknown"
        contexts.append(ctx)

    click.echo(f"Merging {len(contexts)} conversations…")
    try:
        merged = merge_contexts(contexts, use_llm=not no_llm)
    except HandoverAPIError as e:
        raise click.ClickException(str(e)) from e

    output_path = Path(output_dir)
    targets_to_run: list[str] = list_targets() if target == "all" else [target]

    def _make_target(t_name: str) -> BaseTarget:
        if t_name == "claude-code":
            return ClaudeCodeTarget()
        return get_target(t_name)

    if dry_run:
        click.echo(f"\nMerged goal: {merged.goal or '(none)'}")
        click.echo(f"  Tasks: {len(merged.tasks)}  Decisions: {len(merged.decisions)}")
        click.echo(f"\nWould write to {output_path}/:")
        for t_name in targets_to_run:
            for p in _make_target(t_name).generate(merged, output_path, dry_run=True):
                click.echo(f"  -> {p.name}")
        click.echo("\nRun without --dry-run to write files.")
    else:
        all_paths: list[Path] = []
        for t_name in targets_to_run:
            all_paths.extend(_make_target(t_name).generate(merged, output_path, dry_run=False))
        names = ", ".join(p.name for p in all_paths)
        click.echo(f"Wrote {names} to {output_path}/")
        click.echo(f"Merged goal: {merged.goal or '(none)'}")


@main.command("pull")
@click.argument("gist_url")
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(),
    default=None,
    help="Directory to write downloaded files (default: cwd)",
)
def pull_command(gist_url: str, output_dir: str | None) -> None:
    """
    Pull a shared handover from a GitHub Gist URL.

    GIST_URL: Full GitHub Gist URL or Gist ID.

    Examples:

      handover pull https://gist.github.com/user/abc123

      handover pull abc123def456 --output ./my-project/
    """
    from handover.publisher import PublisherError
    from handover.publisher import pull as _pull

    resolved_output = Path(output_dir) if output_dir else Path.cwd()

    try:
        written = _pull(gist_url, resolved_output)
    except PublisherError as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Downloaded {len(written)} file(s) to {resolved_output}/:")
    for p in written:
        click.echo(f"  {p.name}")

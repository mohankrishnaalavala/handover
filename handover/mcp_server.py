"""
handover/mcp_server.py

MCP (Model Context Protocol) server that exposes handover as a tool
callable from inside Claude Code.

Requires the optional [mcp] dependency:
  pip install handover[mcp]

Start the server:
  handover mcp
  # or directly:
  python -m handover.mcp_server

Claude Code MCP config (~/.claude/mcp.json):
  {
    "mcpServers": {
      "handover": {
        "command": "handover",
        "args": ["mcp"],
        "env": { "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}" }
      }
    }
  }

v1.1.1 — four tools are exposed:
  - run_handover       : parse a chat export and generate agent context files
  - handover_status    : read .handover/work/backlog.json and report progress
  - handover_reverse   : summarise the most recent Claude Code session
  - handover_list      : list conversations inside a chat export file

Design rule: every @mcp.tool() wrapper delegates to a plain `*_impl` function
so the impl can be unit-tested without the MCP SDK installed.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Tool 1 — run_handover (existing, with a small v1.1.1 output update)
# ---------------------------------------------------------------------------


def run_handover_impl(
    input_file: str,
    output_dir: str = ".",
    source: str = "auto",
    target: str = "claude-code",
    no_llm: bool = False,
) -> str:
    """
    Core pipeline logic for the handover MCP tool.

    Separated from the @mcp.tool() decorator so it can be tested independently.

    Args:
        input_file: Path to the chat export file (.json, .jsonl, .md).
        output_dir: Directory to write output files (default: current directory).
        source: Parser to use — 'auto' (detect), 'claude', 'chatgpt', 'gemini',
                'perplexity'. Default: 'auto'.
        target: Output format — 'claude-code', 'codex', 'aider', 'goose', 'all'.
                Default: 'claude-code'.
        no_llm: If True, use rule-based extraction without calling the LLM.
                Default: False.

    Returns:
        A summary of what was generated, including file paths. When the
        v1.1.0 two-layer scaffold is produced, the summary also lists the
        `.handover/` subdirectories and the `.claude/` workspace counts.
    """
    from handover.models import HandoverAPIError
    from handover.parsers import detect_source, get_parser
    from handover.targets import get_target, list_targets
    from handover.targets.claude_code import ClaudeCodeTarget

    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        return f"Error: input file not found: {input_file}"

    output_path = Path(output_dir).expanduser().resolve()

    # Auto-detect source
    src = source
    if src == "auto":
        try:
            src = detect_source(str(input_path))
        except ValueError as e:
            return f"Error: {e}"

    parser = get_parser(src)
    try:
        messages = parser.parse(input_path)
    except (ValueError, FileNotFoundError) as e:
        return f"Error parsing {input_file}: {e}"

    if not messages:
        return "Error: no messages found in the export file."

    from handover import summarizer as _summarizer

    try:
        context = _summarizer.summarize(messages, use_llm=not no_llm)
    except HandoverAPIError as e:
        return f"Error during summarization: {e}"

    context.source = src
    context.source_version = parser.detect_format_version(input_path)

    # v1.1.0 — extract a ScaffoldContext so we produce both layers
    # (.handover/ and the per-target .claude/ workspace), mirroring the CLI.
    from handover.scaffold_extractor import extract_scaffold

    try:
        scaffold = extract_scaffold(
            messages,
            context,
            use_llm=not no_llm,
            target=target,
        )
    except HandoverAPIError as e:
        return f"Error during scaffold extraction: {e}"

    from handover.targets.base import BaseTarget
    from handover.universal_generator import HandoverDirExistsError, write_handover_dir

    all_paths: list[Path] = []
    try:
        all_paths.extend(write_handover_dir(scaffold, output_path, overwrite=True))
    except HandoverDirExistsError as e:
        return f"Error writing .handover/: {e}"

    targets_to_run = list_targets() if target == "all" else [target]
    for t_name in targets_to_run:
        t_obj: BaseTarget
        if t_name == "claude-code":
            t_obj = ClaudeCodeTarget(scaffold=scaffold, overwrite_workspace=True)
        else:
            t_obj = get_target(t_name)
        all_paths.extend(t_obj.generate(context, output_path, dry_run=False))

    # v1.1.2 — run codebase indexer as the last step
    idx = None
    try:
        from handover.indexer import index_project

        idx = index_project(output_path)
    except Exception:  # noqa: BLE001 — indexer errors should not break the pipeline
        pass

    lines = [f"Generated {len(all_paths)} files in {output_path}/"]

    handover_dir = output_path / ".handover"
    if handover_dir.is_dir():
        subdirs = sorted(
            {
                p.parent.relative_to(handover_dir).parts[0]
                for p in handover_dir.rglob("*")
                if p.is_file() and p.parent != handover_dir
            }
        )
        if subdirs:
            lines.append(f"  .handover/: {', '.join(subdirs)}")

    claude_dir = output_path / ".claude"
    if claude_dir.is_dir():
        workspace_counts: list[str] = []
        for subname, suffix in (
            ("agents", "agents"),
            ("skills", "skills"),
            ("commands", "commands"),
            ("hooks", "hooks"),
        ):
            sub = claude_dir / subname
            if sub.is_dir():
                n = sum(1 for _ in sub.iterdir() if _.is_file())
                if n > 0:
                    workspace_counts.append(f"{n} {suffix}")
        if workspace_counts:
            lines.append(f"  .claude/: {', '.join(workspace_counts)}")

    if idx is not None:
        lines.append(
            f"  .handover/codebase/: {idx.stats['total_files']} files, "
            f"{len(idx.symbols)} symbols"
        )

    lines.append(f"Goal: {context.goal or '(none detected)'}")
    lines.append(
        f"Tasks: {len(context.tasks)}  "
        f"Decisions: {len(context.decisions)}  "
        f"Tech stack: {', '.join(context.tech_stack.values()) or '(none)'}"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2 — handover_status (new in v1.1.1)
# ---------------------------------------------------------------------------


def handover_status_impl(project_dir: str = ".") -> str:
    """
    Read `.handover/work/backlog.json` and return a progress summary.

    This is the "live dashboard" tool: call it from chat to answer
    "where are we?" without switching to the terminal.

    Args:
        project_dir: Path to the project directory containing
            `.handover/work/backlog.json`. Defaults to the current directory.

    Returns:
        A multi-line string summarising progress. If no backlog is found
        the string starts with "No backlog.json found".
    """
    resolved = Path(project_dir).expanduser().resolve()
    backlog_path = resolved / ".handover" / "work" / "backlog.json"
    if not backlog_path.exists():
        return f"No backlog.json found in {resolved}/.handover/work/. Run handover first."

    try:
        data = json.loads(backlog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return f"Error reading {backlog_path}: {e}"

    tasks = data.get("tasks", []) or []
    total = len(tasks)
    done = [t for t in tasks if t.get("done")]
    remaining = [t for t in tasks if not t.get("done")]
    high_pri = [t for t in remaining if t.get("priority") == "high"]

    project_label = data.get("project") or str(resolved)
    lines = [
        f"Project: {project_label}",
        f"Progress: {len(done)}/{total} tasks complete",
        "",
    ]

    if high_pri:
        lines.append("High priority remaining:")
        for t in high_pri[:5]:
            lines.append(f"  • {t.get('title', '(untitled)')}")
        lines.append("")

    if remaining:
        lines.append(f"Next task: {remaining[0].get('title', '(untitled)')}")

    last: dict[str, object] | None = None
    if done:
        last = done[-1]
        lines.append(f"Last completed: {last.get('title', '(untitled)')}")
        if last.get("done_at"):
            lines.append(f"  at {str(last['done_at'])[:10]}")

    # v1.1.2 — change impact from codebase index
    deps_path = resolved / ".handover" / "codebase" / "dependencies.json"
    if deps_path.exists() and last and last.get("changed_files"):
        try:
            deps = json.loads(deps_path.read_text(encoding="utf-8"))
            impact = deps.get("change_impact", {})
            at_risk: set[str] = set()
            changed = last.get("changed_files", [])
            for f in changed if isinstance(changed, list) else []:
                ci = impact.get(f) or {}
                at_risk.update(ci.get("direct_dependents", []))
                at_risk.update(ci.get("affected_tests", []))
            if at_risk:
                lines.append("At risk:")
                for risk_file in sorted(at_risk)[:5]:
                    lines.append(f"  • {risk_file}")
        except (OSError, json.JSONDecodeError):
            pass

    lines.append("")
    lines.append(f"Full task list: {backlog_path}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3 — handover_reverse (new in v1.1.1)
# ---------------------------------------------------------------------------


def handover_reverse_impl(
    project_dir: str = ".",
    output_dir: str = "",
    no_llm: bool = False,
) -> str:
    """
    Generate a HANDOVER.md from the most recent Claude Code session.

    Wraps the existing `reverse()` orchestrator and `Generator.generate_handover()`
    — no new logic, just MCP exposure.

    Args:
        project_dir: Project root. Used to discover the most recent
            Claude Code session via `~/.claude/projects/<hash>/`.
        output_dir: Where to write HANDOVER.md. Defaults to `project_dir`.
        no_llm: If True, use heuristic extraction only (no API cost).

    Returns:
        A short summary of the reverse handover, or an informative error
        string if no sessions were found or parsing failed.
    """
    from handover.generator import Generator
    from handover.parsers.claude_code import ClaudeCodeSessionParser
    from handover.reverse import reverse

    resolved_project = Path(project_dir).expanduser().resolve()
    resolved_output = Path(output_dir).expanduser().resolve() if output_dir else resolved_project

    parser = ClaudeCodeSessionParser()
    sessions = parser.discover_sessions(resolved_project)
    if not sessions:
        return (
            f"No Claude Code sessions found for {resolved_project}. "
            "Run a Claude Code session first."
        )

    session_file = sessions[0].file_path
    try:
        context = reverse(session_file, resolved_project, use_llm=not no_llm)
    except Exception as e:  # noqa: BLE001 — surface any pipeline failure
        return f"Error reading session: {e}"

    try:
        Generator().generate_handover(context, resolved_output, dry_run=False)
    except Exception as e:  # noqa: BLE001 — surface generator/template errors
        return f"Error writing HANDOVER.md: {e}"

    session_short = (context.session_id or "")[:8] or "(unknown)"
    lines = [
        f"Session: {session_short}  Branch: {context.git_branch or '(unknown)'}",
        f"Files changed: {len(context.files_changed)}",
        f"Commands run: {len(context.commands_run)}",
        "",
    ]
    if context.decisions:
        lines.append("Key decisions made:")
        for d in context.decisions[:3]:
            lines.append(f"  • {d}")
        lines.append("")
    if context.next_steps:
        lines.append("Recommended next steps:")
        for step in context.next_steps[:3]:
            lines.append(f"  {step}")
        lines.append("")
    lines.append(f"Full summary written to: {resolved_output}/HANDOVER.md")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4 — handover_list (new in v1.1.1)
# ---------------------------------------------------------------------------


def handover_list_impl(input_file: str) -> str:
    """
    List conversations available in a chat export file.

    Lets the user say "show me what's in my Claude export" from chat.

    Args:
        input_file: Path to the chat export file (.json or .jsonl).

    Returns:
        A multi-line string listing up to 20 conversations with id/date/title,
        or an error string if the file is missing or unreadable.
    """
    from handover.parsers import detect_source, get_parser

    path = Path(input_file).expanduser().resolve()
    if not path.exists():
        return f"File not found: {input_file}"

    try:
        source = detect_source(str(path))
        parser = get_parser(source)
        conversations = parser.list_conversations(path)
    except Exception as e:  # noqa: BLE001 — parser errors are user-facing
        return f"Error reading {input_file}: {e}"

    if not conversations:
        return "No conversations found."

    lines = [f"Found {len(conversations)} conversation(s) in {path.name}:", ""]
    for conv in conversations[:20]:
        conv_id = str(conv.get("id", ""))[:12]
        date_raw = conv.get("date") or ""
        date = date_raw[:10] if date_raw else "unknown"
        title = conv.get("title", "Untitled")
        lines.append(f"  {conv_id:<12}  {date:<10}  {title}")

    if len(conversations) > 20:
        lines.append(f"  ... and {len(conversations) - 20} more")

    lines.append("")
    lines.append("Use run_handover with id= or title= to generate workspace.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# FastMCP entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the MCP server."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("MCP package not installed. Run: pip install handover[mcp]") from exc

    mcp = FastMCP(
        "handover",
        instructions=(
            "Parse AI chat exports (Claude, ChatGPT, Gemini, Perplexity) and "
            "generate project workspaces, or query an existing project's task "
            "status, reverse-summarise a Claude Code session, or list the "
            "conversations inside a chat export."
        ),
    )

    @mcp.tool()
    def run_handover(
        input_file: str,
        output_dir: str = ".",
        source: str = "auto",
        target: str = "claude-code",
        no_llm: bool = False,
    ) -> str:
        """
        Parse an AI chat export and generate agent context files.

        Args:
            input_file: Path to the chat export file (.json, .jsonl, .md).
            output_dir: Directory to write output files (default: current directory).
            source: Parser to use — 'auto' (detect), 'claude', 'chatgpt', 'gemini',
                    'perplexity'. Default: 'auto'.
            target: Output format — 'claude-code', 'codex', 'aider', 'goose', 'all'.
                    Default: 'claude-code'.
            no_llm: If True, use rule-based extraction without calling the LLM.
                    Default: False.

        Returns:
            A summary of what was generated, including file paths.
        """
        return run_handover_impl(
            input_file=input_file,
            output_dir=output_dir,
            source=source,
            target=target,
            no_llm=no_llm,
        )

    @mcp.tool()
    def handover_status(project_dir: str = ".") -> str:
        """
        Report task progress from `.handover/work/backlog.json`.

        Args:
            project_dir: Project directory containing `.handover/work/backlog.json`.
                Defaults to the current directory.

        Returns:
            A progress summary (total/done/remaining, high-priority, next task,
            last completed). If no backlog is found the response says so.
        """
        return handover_status_impl(project_dir=project_dir)

    @mcp.tool()
    def handover_reverse(
        project_dir: str = ".",
        output_dir: str = "",
        no_llm: bool = False,
    ) -> str:
        """
        Summarise the most recent Claude Code session for `project_dir`.

        Writes `HANDOVER.md` into `output_dir` (or `project_dir` when empty)
        and returns a short summary.

        Args:
            project_dir: Project root. The most recent Claude Code session
                for this project is auto-discovered.
            output_dir: Where to write `HANDOVER.md`. Defaults to `project_dir`.
            no_llm: If True, use heuristic extraction only (no API cost).

        Returns:
            A short text summary, or an error string if no session was found.
        """
        return handover_reverse_impl(
            project_dir=project_dir,
            output_dir=output_dir,
            no_llm=no_llm,
        )

    @mcp.tool()
    def handover_list(input_file: str) -> str:
        """
        List conversations available in a chat export file.

        Args:
            input_file: Path to a chat export file (.json or .jsonl).

        Returns:
            A multi-line list of up to 20 conversations, or an error string.
        """
        return handover_list_impl(input_file=input_file)

    mcp.run()


if __name__ == "__main__":
    main()

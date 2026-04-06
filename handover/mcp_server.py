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

Phase 6 — Ecosystem & Developer Experience.
"""

from __future__ import annotations

from pathlib import Path

from handover import __version__


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
        A summary of what was generated, including file paths.
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

    targets_to_run = list_targets() if target == "all" else [target]
    all_paths: list[Path] = []
    for t_name in targets_to_run:
        t_obj = ClaudeCodeTarget() if t_name == "claude-code" else get_target(t_name)
        all_paths.extend(t_obj.generate(context, output_path, dry_run=False))

    written = ", ".join(p.name for p in all_paths)
    return (
        f"Generated {written} in {output_path}/\n"
        f"Goal: {context.goal or '(none detected)'}\n"
        f"Tasks: {len(context.tasks)}  "
        f"Decisions: {len(context.decisions)}  "
        f"Tech stack: {', '.join(context.tech_stack.values()) or '(none)'}"
    )


def main() -> None:
    """Entry point for the MCP server."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("MCP package not installed. Run: pip install handover[mcp]") from exc

    mcp = FastMCP(
        "handover",
        version=__version__,
        description=(
            "Parse an AI chat export (Claude, ChatGPT, Gemini, Perplexity) and "
            "generate CLAUDE.md + PLAN.md or other agent context files."
        ),
    )

    @mcp.tool()  # type: ignore[untyped-decorator]
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

    mcp.run()


if __name__ == "__main__":
    main()

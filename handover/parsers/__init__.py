"""
handover/parsers/__init__.py

Parser adapter registry.
See PRD Section 6 — Architecture (Parser component).

To add a new source adapter:
  1. Create handover/parsers/{source_name}.py
  2. Subclass BaseParser
  3. Register it in ADAPTER_REGISTRY below
  4. Follow the full guide in docs/adding-an-adapter.md
"""

from pathlib import Path

from handover.parsers.base import BaseParser
from handover.parsers.claude import ClaudeParser

ADAPTER_REGISTRY: dict[str, type[BaseParser]] = {
    "claude": ClaudeParser,
    # "chatgpt": ChatGPTParser,   # Phase 2
    # "gemini": GeminiParser,     # Phase 2
}


def get_parser(source: str) -> BaseParser:
    """
    Return an instantiated parser for the given source name.

    Args:
        source: Source identifier string (e.g. "claude", "chatgpt").

    Returns:
        An instantiated BaseParser subclass.

    Raises:
        ValueError: If no adapter is registered for the given source.
    """
    if source not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"No adapter registered for source '{source}'. Available sources: {available}"
        )
    return ADAPTER_REGISTRY[source]()


def detect_source(file_path: str) -> str:
    """
    Auto-detect the source from a file's extension and content.

    Args:
        file_path: Path to the export file.

    Returns:
        Source identifier string (e.g. "claude").

    Raises:
        ValueError: If the format cannot be detected.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".jsonl":
        # Only Claude uses JSONL with the uuid/chat_messages schema
        return "claude"

    if suffix == ".json":
        try:
            snippet = path.read_text(encoding="utf-8")[:500]
            if '"uuid"' in snippet or '"chat_messages"' in snippet:
                return "claude"
        except OSError:
            pass
        raise ValueError(
            f"Could not auto-detect source from {path.name}. "
            "Use --source claude to specify explicitly."
        )

    if suffix == ".md":
        try:
            snippet = path.read_text(encoding="utf-8")[:500]
            if "**Human:**" in snippet or "**Assistant:**" in snippet:
                return "claude"
        except OSError:
            pass
        raise ValueError(
            f"Could not auto-detect source from {path.name}. "
            "Use --source claude to specify explicitly."
        )

    raise ValueError(
        f"Unsupported file extension {suffix!r}. Supported formats: .json, .jsonl, .md"
    )

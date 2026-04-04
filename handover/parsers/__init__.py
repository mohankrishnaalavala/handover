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

from handover.parsers.base import BaseParser
from handover.parsers.claude import ClaudeParser

# TODO: implement — add new adapters here as they are contributed

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
    # TODO: implement
    if source not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"No adapter registered for source '{source}'. "
            f"Available sources: {available}"
        )
    return ADAPTER_REGISTRY[source]()


def detect_source(file_path: str) -> str:
    """
    Auto-detect the source from a file's contents.

    Args:
        file_path: Path to the export file.

    Returns:
        Source identifier string (e.g. "claude").

    Raises:
        ValueError: If the format cannot be detected.
    """
    # TODO: implement auto-detection logic — see PRD Section 6
    raise NotImplementedError("Auto-detection not yet implemented")

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
from handover.parsers.chatgpt import ChatGPTParser
from handover.parsers.claude import ClaudeParser
from handover.parsers.gemini import GeminiParser
from handover.parsers.perplexity import PerplexityParser

ADAPTER_REGISTRY: dict[str, type[BaseParser]] = {
    "claude": ClaudeParser,
    "chatgpt": ChatGPTParser,
    "gemini": GeminiParser,
    "perplexity": PerplexityParser,
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

    Priority ladder (checked in order):
      1. Claude:      .jsonl  OR  .json with "uuid"/"chat_messages"  OR  .md with **Human:**
      2. ChatGPT:     .json with "mapping" key + author.role node
      3. Gemini:      .json with "appActivity" key OR "Gemini Apps" in first 500 bytes
      4. Perplexity:  .json with "conversations" key + ("sources" in content OR perplexity_ prefix)
      5. else:        raise ValueError

    Args:
        file_path: Path to the export file.

    Returns:
        Source identifier string (e.g. "claude", "chatgpt").

    Raises:
        ValueError: If the format cannot be detected.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".jsonl":
        return "claude"

    if suffix == ".md":
        try:
            snippet = path.read_text(encoding="utf-8")[:500]
            if "**Human:**" in snippet or "**Assistant:**" in snippet:
                return "claude"
        except OSError:
            pass
        raise ValueError(
            f"Could not auto-detect source from {path.name}. Use --source to specify explicitly."
        )

    if suffix == ".json":
        try:
            snippet = path.read_text(encoding="utf-8")[:500]
        except OSError as exc:
            raise ValueError(f"Could not read {path.name}.") from exc

        # 1. Claude
        if '"uuid"' in snippet or '"chat_messages"' in snippet:
            return "claude"

        # 2. ChatGPT: has "mapping" key and at least one node with author.role
        if '"mapping"' in snippet and '"author"' in snippet:
            return "chatgpt"

        # 3. Gemini: has "appActivity" key or "Gemini Apps" literal
        if '"appActivity"' in snippet or "Gemini Apps" in snippet:
            return "gemini"

        # 4. Perplexity: has "conversations" key AND (sources field OR filename prefix)
        if '"conversations"' in snippet and (
            '"sources"' in snippet or path.name.startswith("perplexity_")
        ):
            return "perplexity"

        raise ValueError(
            f"Could not auto-detect source from {path.name}. "
            "Use --source (claude, chatgpt, gemini, perplexity) to specify explicitly."
        )

    raise ValueError(
        f"Unsupported file extension {suffix!r}. Supported formats: .json, .jsonl, .md"
    )

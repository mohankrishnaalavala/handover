"""
handover/parsers/base.py

Abstract base class for all source adapters.
See PRD Section 6 — Architecture (Parser component).

All adapters must subclass BaseParser and implement the parse() method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from handover.models import ConversationMessage

# TODO: implement — see PRD Section 6


class BaseParser(ABC):
    """
    Abstract base class for all handover source adapters.

    Each adapter handles one chat export source (Claude, ChatGPT, Gemini, ...).
    Adapters are responsible for reading the raw export file and returning
    a normalized list of ConversationMessage objects in chronological order.
    """

    source_name: str = ""   # Must be set by each subclass (e.g. "claude", "chatgpt")

    @abstractmethod
    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a chat export file and return normalized messages.

        Args:
            file_path: Path to the export file.

        Returns:
            List of ConversationMessage objects in chronological order.

        Raises:
            ValueError: If the file format is unrecognized or unsupported.
            FileNotFoundError: If the file does not exist.
        """
        # TODO: implement in subclass
        raise NotImplementedError

    def detect_format_version(self, file_path: Path) -> str:
        """
        Detect the export format version from the file contents.

        Used to populate HandoverContext.source_version.
        Override in subclasses that support multiple format versions.

        Args:
            file_path: Path to the export file.

        Returns:
            Version string (e.g. "1.0", "2.0") or "unknown".
        """
        # TODO: implement in subclass if applicable
        return "unknown"

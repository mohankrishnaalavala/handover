"""
handover/targets/base.py

Abstract base class for target adapters.
Each target knows how to render a HandoverContext into agent-specific files.

Phase 5 — Multi-Target Agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from handover.models import HandoverContext


class BaseTarget(ABC):
    """Abstract base class that every target adapter must subclass."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Target identifier used in the --target flag (e.g. 'claude-code')."""
        ...

    @abstractmethod
    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate target-specific files from the given HandoverContext.

        Args:
            context: Fully extracted HandoverContext from the summarizer.
            output_dir: Directory where output files should be written.
            dry_run: If True, return expected paths without writing files.

        Returns:
            List of Paths that were (or would be) written.
        """
        ...

    def describe(self) -> dict[str, str]:
        """
        Return human-readable metadata about this target.

        Override to provide a richer description for help text or introspection.

        Returns:
            A dict with at minimum 'name' and 'description' keys.
        """
        return {"name": self.name, "description": ""}

"""
handover/indexers/generic_indexer.py

Fallback indexer for file types without a dedicated parser.
Lists the file with line count but extracts no symbols or imports.
"""

from __future__ import annotations

from pathlib import Path

from handover.models import FileIndex, Symbol

from .base import BaseIndexer


class GenericIndexer(BaseIndexer):
    """Fallback indexer — accepts any file, extracts no symbols."""

    extensions = ()  # empty — relies on can_index override

    def can_index(self, path: Path) -> bool:  # noqa: ARG002
        """Always returns True — this is the last-resort indexer."""
        return True

    def index_file(
        self,
        path: Path,
        project_root: Path,
        all_module_paths: set[Path],  # noqa: ARG002
    ) -> tuple[FileIndex, list[Symbol]]:
        """Return a minimal FileIndex with line count only."""
        rel_path = str(path.relative_to(project_root))
        try:
            line_count = len(path.read_bytes().split(b"\n"))
        except OSError:
            line_count = 0

        return (
            FileIndex(
                path=rel_path,
                purpose="",
                line_count=line_count,
            ),
            [],
        )

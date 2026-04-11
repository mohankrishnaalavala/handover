"""
handover/indexers/base.py

Abstract base class for language-specific file indexers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from handover.models import FileIndex, Symbol


class BaseIndexer(ABC):
    """Abstract base for language-specific indexers.

    Subclasses declare which file extensions they handle and implement
    ``index_file`` to extract structure and symbols.
    """

    extensions: tuple[str, ...] = ()

    def can_index(self, path: Path) -> bool:
        """Return True if this indexer handles files with *path*'s extension."""
        return path.suffix in self.extensions

    @abstractmethod
    def index_file(
        self,
        path: Path,
        project_root: Path,
        all_module_paths: set[Path],
    ) -> tuple[FileIndex, list[Symbol]]:
        """Index a single source file.

        Args:
            path: Absolute path to the file.
            project_root: Project root directory (for resolving internal imports).
            all_module_paths: Set of all source-file paths in the project
                (used by the Python indexer to classify imports as internal).

        Returns:
            A ``(FileIndex, list[Symbol])`` tuple.
        """
        ...

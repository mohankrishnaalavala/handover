"""
handover/indexers/__init__.py

Indexer registry and file-discovery utilities.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from .base import BaseIndexer
from .generic_indexer import GenericIndexer
from .python_indexer import PythonIndexer
from .typescript_indexer import TypeScriptIndexer

__all__ = [
    "INDEXER_REGISTRY",
    "BaseIndexer",
    "GenericIndexer",
    "PythonIndexer",
    "TypeScriptIndexer",
    "detect_indexer",
    "get_all_source_files",
]

# Order matters — GenericIndexer must be last (it accepts everything).
INDEXER_REGISTRY: list[BaseIndexer] = [
    PythonIndexer(),
    TypeScriptIndexer(),
    GenericIndexer(),
]

# Directories always excluded from indexing.
EXCLUDED_DIRS: set[str] = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".git",
    ".handover",
    ".claude",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "egg-info",
}

# Maximum line count — files larger than this are listed but not symbolised.
MAX_LINES = 500


def detect_indexer(path: Path) -> BaseIndexer:
    """Return the first indexer that can handle *path*."""
    for indexer in INDEXER_REGISTRY:
        if indexer.can_index(path):
            return indexer
    # GenericIndexer.can_index always returns True, so we never reach here,
    # but satisfy the type checker anyway.
    return INDEXER_REGISTRY[-1]  # pragma: no cover


def get_all_source_files(
    project_dir: Path,
    exclude_globs: tuple[str, ...] = (),
) -> list[Path]:
    """Walk *project_dir* and return indexable source files.

    Skips:
      - directories in ``EXCLUDED_DIRS``
      - binary files (null byte in first 1 KB)
      - files > ``MAX_LINES`` lines
      - files matching any pattern in *exclude_globs*
    """
    results: list[Path] = []

    if not project_dir.is_dir():
        return results

    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue

        # Skip files inside excluded directories
        if _in_excluded_dir(path, project_dir):
            continue

        # Skip user-supplied exclude globs
        rel = str(path.relative_to(project_dir))
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude_globs):
            continue

        # Skip binary files
        if _is_binary(path):
            continue

        # Skip files over MAX_LINES
        if _over_max_lines(path):
            continue

        results.append(path)

    return results


def _in_excluded_dir(path: Path, project_root: Path) -> bool:
    """Return True if *path* is inside any excluded directory."""
    try:
        rel_parts = path.relative_to(project_root).parts
    except ValueError:
        return False
    return any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel_parts)


def _is_binary(path: Path) -> bool:
    """Return True if the file looks like a binary (null byte in first 1 KB)."""
    try:
        chunk = path.read_bytes()[:1024]
        return b"\x00" in chunk
    except OSError:
        return True


def _over_max_lines(path: Path) -> bool:
    """Return True if the file has more than ``MAX_LINES`` lines."""
    try:
        return len(path.read_bytes().split(b"\n")) > MAX_LINES
    except OSError:
        return True

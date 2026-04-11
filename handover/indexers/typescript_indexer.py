"""
handover/indexers/typescript_indexer.py

Regex-based TypeScript/JavaScript file indexer.
Approximate — extracts exports, imports, and line counts.
"""

from __future__ import annotations

import re
from pathlib import Path

from handover.models import FileIndex, Symbol

from .base import BaseIndexer

# Compiled regex patterns
EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?"
    r"(?:function|class|const|let|var|interface|type|enum)\s+(\w+)",
    re.MULTILINE,
)

IMPORT_RE = re.compile(
    r"""^import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)


class TypeScriptIndexer(BaseIndexer):
    """Index TypeScript and JavaScript files using regex."""

    extensions = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

    def index_file(
        self,
        path: Path,
        project_root: Path,
        all_module_paths: set[Path],
    ) -> tuple[FileIndex, list[Symbol]]:
        """Parse *path* with regex and extract exports/imports."""
        rel_path = str(path.relative_to(project_root))

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return (
                FileIndex(path=rel_path, purpose="(read error)"),
                [],
            )

        line_count = source.count("\n") + 1

        # Extract exports
        exports: list[str] = []
        symbols: list[Symbol] = []
        for match in EXPORT_RE.finditer(source):
            name = match.group(1)
            if name not in exports:
                exports.append(name)
                line_no = source[: match.start()].count("\n") + 1
                symbols.append(
                    Symbol(
                        name=name,
                        type="function",
                        file=rel_path,
                        line=line_no,
                        signature="(approximate)",
                        docstring="",
                    )
                )

        # Classify imports
        imports_internal: list[str] = []
        imports_external: list[str] = []
        for match in IMPORT_RE.finditer(source):
            module_path = match.group(1)
            if module_path.startswith((".", "/")):
                if module_path not in imports_internal:
                    imports_internal.append(module_path)
            else:
                pkg = module_path.split("/")[0]
                if pkg not in imports_external:
                    imports_external.append(pkg)

        has_tests, test_file = _find_test_file_ts(path, project_root)

        return (
            FileIndex(
                path=rel_path,
                purpose="",
                exports=exports,
                imports_internal=imports_internal,
                imports_external=imports_external,
                line_count=line_count,
                has_tests=has_tests,
                test_file=test_file,
            ),
            symbols,
        )


def _find_test_file_ts(path: Path, project_root: Path) -> tuple[bool, str | None]:
    """Look for a corresponding test file for a TS/JS file."""
    stem = path.stem
    ext = path.suffix
    candidates = [
        path.parent / f"{stem}.test{ext}",
        path.parent / f"{stem}.spec{ext}",
        project_root / "__tests__" / f"{stem}.test{ext}",
        project_root / "tests" / f"{stem}.test{ext}",
    ]
    for c in candidates:
        if c.exists():
            try:
                return True, str(c.relative_to(project_root))
            except ValueError:
                return True, str(c)
    return False, None

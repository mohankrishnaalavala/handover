"""
handover/indexers/python_indexer.py

Precise Python file indexer using the ``ast`` module.
Extracts functions, classes, imports, and module docstrings.
"""

from __future__ import annotations

import ast
from pathlib import Path

from handover.models import FileIndex, Symbol

from .base import BaseIndexer


class PythonIndexer(BaseIndexer):
    """Index ``.py`` files using ``ast.parse()``."""

    extensions = (".py",)

    def index_file(
        self,
        path: Path,
        project_root: Path,
        all_module_paths: set[Path],
    ) -> tuple[FileIndex, list[Symbol]]:
        """Parse *path* and extract structure + symbols."""
        rel_path = str(path.relative_to(project_root))
        line_count = _count_lines(path)

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return (
                FileIndex(
                    path=rel_path,
                    purpose="(parse error)",
                    line_count=line_count,
                ),
                [],
            )

        purpose = _module_purpose(tree)
        exports: list[str] = []
        symbols: list[Symbol] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                exports.append(node.name)
                symbols.append(_symbol_from_func(node, rel_path))
            elif isinstance(node, ast.ClassDef):
                exports.append(node.name)
                symbols.append(_symbol_from_class(node, rel_path))

        imports_internal, imports_external = _classify_imports(
            tree, path, project_root, all_module_paths
        )

        has_tests, test_file = _find_test_file(path, project_root)

        return (
            FileIndex(
                path=rel_path,
                purpose=purpose,
                exports=exports,
                imports_internal=imports_internal,
                imports_external=imports_external,
                line_count=line_count,
                has_tests=has_tests,
                test_file=test_file,
            ),
            symbols,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_lines(path: Path) -> int:
    try:
        return len(path.read_bytes().split(b"\n"))
    except OSError:
        return 0


def _module_purpose(tree: ast.Module) -> str:
    """Return the first non-empty line of the module docstring, or ``""``."""
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _symbol_from_func(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    rel_path: str,
) -> Symbol:
    sig = _reconstruct_signature(node)
    return Symbol(
        name=node.name,
        type="function",
        file=rel_path,
        line=node.lineno,
        signature=sig,
        docstring=ast.get_docstring(node) or "",
    )


def _symbol_from_class(node: ast.ClassDef, rel_path: str) -> Symbol:
    bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
    sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
    return Symbol(
        name=node.name,
        type="class",
        file=rel_path,
        line=node.lineno,
        signature=sig[:200],
        docstring=ast.get_docstring(node) or "",
    )


def _reconstruct_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstruct the function signature from AST (body stripped)."""
    try:
        full = ast.unparse(node)
    except Exception:  # noqa: BLE001
        return f"def {node.name}(...)"
    # Take up to the first colon after the closing paren
    first_line = full.split("\n")[0]
    sig = first_line.rstrip()
    # Remove trailing colon and body hints
    if sig.endswith(":"):
        sig = sig[:-1].rstrip()
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    if not sig.startswith(("def ", "async ")):
        sig = f"{prefix}def {node.name}(...)"
    return sig[:200]


def _classify_imports(
    tree: ast.Module,
    file_path: Path,
    project_root: Path,
    all_module_paths: set[Path],
) -> tuple[list[str], list[str]]:
    """Walk import nodes and classify as internal or external."""
    internal: list[str] = []
    external: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                # Check if top-level module resolves to a project file
                candidate = project_root / name.replace(".", "/")
                if (
                    candidate.with_suffix(".py") in all_module_paths
                    or (candidate / "__init__.py") in all_module_paths
                ):
                    if alias.name not in internal:
                        internal.append(alias.name)
                elif name not in external:
                    external.append(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import → always internal
                module_name = node.module or ""
                rel_str = "." * node.level + module_name
                if rel_str not in internal:
                    internal.append(rel_str)
                # Also resolve to a concrete path for the graph
                _resolve_relative_import(file_path, project_root, node.level, node.module, internal)
            elif node.module:
                top = node.module.split(".")[0]
                candidate = project_root / top.replace(".", "/")
                if (
                    candidate.with_suffix(".py") in all_module_paths
                    or (candidate / "__init__.py") in all_module_paths
                ):
                    if node.module not in internal:
                        internal.append(node.module)
                elif top not in external:
                    external.append(top)

    return internal, external


def _resolve_relative_import(
    file_path: Path,
    project_root: Path,
    level: int,
    module: str | None,
    internal: list[str],
) -> None:
    """Best-effort resolution of a relative import to a project-relative path."""
    base = file_path.parent
    for _ in range(level - 1):
        base = base.parent
    if module:
        parts = module.split(".")
        resolved = base / "/".join(parts)
        # Try as .py or as package
        for candidate in (resolved.with_suffix(".py"), resolved / "__init__.py"):
            if candidate.exists():
                try:
                    rel = str(candidate.relative_to(project_root))
                    if rel not in internal:
                        internal.append(rel)
                except ValueError:
                    pass
                break


def _find_test_file(path: Path, project_root: Path) -> tuple[bool, str | None]:
    """Look for a corresponding test file."""
    stem = path.stem
    # Common patterns: tests/test_<stem>.py adjacent or under project root
    candidates = [
        path.parent / f"test_{stem}.py",
        project_root / "tests" / f"test_{stem}.py",
        project_root / "test" / f"test_{stem}.py",
    ]
    for c in candidates:
        if c.exists():
            try:
                return True, str(c.relative_to(project_root))
            except ValueError:
                return True, str(c)
    return False, None

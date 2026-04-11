"""
handover/indexer.py

Codebase indexer — scans a project directory and writes
``.handover/codebase/`` with structure, symbols, dependencies, and a
human-readable index.

Public API:
    index_project(project_dir, output_dir, ...) → CodebaseIndex | None
    refresh_index(project_dir) → CodebaseIndex | None

Runs locally — no API calls.  Introduced in v1.1.2.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from handover.indexers import detect_indexer, get_all_source_files
from handover.models import (
    ChangeImpact,
    CodebaseIndex,
    DependencyNode,
    FileIndex,
    Symbol,
)

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates" / "handover"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def index_project(
    project_dir: Path,
    output_dir: Path | None = None,
    *,
    dry_run: bool = False,
    exclude: tuple[str, ...] = (),
    overwrite: bool = True,
) -> CodebaseIndex | None:
    """Analyse *project_dir* and write ``.handover/codebase/`` files.

    Args:
        project_dir: Root of the project to index.
        output_dir: Where to write ``.handover/codebase/``.
            Defaults to *project_dir*.
        dry_run: If True, return ``CodebaseIndex`` without writing files.
        exclude: Additional glob patterns to exclude (on top of defaults).
        overwrite: Ignored for now — always overwrites.

    Returns:
        ``CodebaseIndex`` if *project_dir* has source files, ``None`` otherwise.
    """
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        logger.info("Project dir does not exist: %s — skipping codebase index.", project_dir)
        return None

    source_files = get_all_source_files(project_dir, exclude_globs=exclude)
    if not source_files:
        logger.info("No source files found in %s — skipping codebase index.", project_dir)
        return None

    resolved_output = (output_dir or project_dir).resolve()

    # Pre-compute the set of all module paths for Python import classification.
    all_module_paths: set[Path] = {p for p in source_files if p.suffix == ".py"}

    # Index every file.
    files: dict[str, FileIndex] = {}
    symbols: list[Symbol] = []

    for path in source_files:
        indexer = detect_indexer(path)
        file_index, file_symbols = indexer.index_file(path, project_dir, all_module_paths)
        files[file_index.path] = file_index
        symbols.extend(file_symbols)

    # Build dependency graph and change impact.
    graph = _build_dependency_graph(files)
    impact = _compute_change_impact(graph, files)
    stats = _compute_stats(files)

    index = CodebaseIndex(
        schema_version="1.0",
        indexed_at=datetime.now(tz=UTC).isoformat(),
        root=str(project_dir),
        files=files,
        symbols=symbols,
        dependency_graph=graph,
        change_impact=impact,
        stats=stats,
    )

    if not dry_run:
        _write_codebase_dir(index, resolved_output)

    return index


def refresh_index(project_dir: Path) -> CodebaseIndex | None:
    """Re-index an existing project (convenience wrapper)."""
    return index_project(project_dir, overwrite=True)


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


def _build_dependency_graph(files: dict[str, FileIndex]) -> dict[str, DependencyNode]:
    """Build the internal dependency graph by inverting ``imports_internal``."""
    graph: dict[str, DependencyNode] = {}

    # Initialise nodes for every file.
    for path in files:
        graph[path] = DependencyNode()

    # For each file, record what it depends on and update the inverse.
    for path, findex in files.items():
        for imp in findex.imports_internal:
            # Resolve the import to a known file path.
            resolved = _resolve_import_to_path(imp, files)
            if resolved and resolved != path:
                if resolved not in graph[path].depends_on:
                    graph[path].depends_on.append(resolved)
                if resolved in graph and path not in graph[resolved].depended_on_by:
                    graph[resolved].depended_on_by.append(path)

    return graph


def _resolve_import_to_path(import_str: str, files: dict[str, FileIndex]) -> str | None:
    """Best-effort: map an import string to a known file path in *files*."""
    # Direct match (import string IS the file path)
    if import_str in files:
        return import_str

    # Try treating it as a module path (dots → slashes)
    as_path = import_str.lstrip(".").replace(".", "/")
    # foo.bar → foo/bar.py or foo/bar/__init__.py
    candidates = [
        as_path + ".py",
        as_path + "/__init__.py",
    ]
    for c in candidates:
        if c in files:
            return c

    # Partial match — import names a parent package
    for file_path in files:
        if file_path.startswith(as_path + "/"):
            return file_path

    return None


# ---------------------------------------------------------------------------
# Change impact
# ---------------------------------------------------------------------------


def _compute_change_impact(
    graph: dict[str, DependencyNode],
    files: dict[str, FileIndex],
) -> dict[str, ChangeImpact]:
    """Compute change-impact risk for every file."""
    impact: dict[str, ChangeImpact] = {}

    for path, node in graph.items():
        direct_deps = list(node.depended_on_by)
        affected_tests: list[str] = []

        # Collect test files of direct dependents.
        for dep_path in direct_deps:
            dep_file = files.get(dep_path)
            if dep_file and dep_file.test_file and dep_file.test_file not in affected_tests:
                affected_tests.append(dep_file.test_file)

        # Also include own test file if present.
        own = files.get(path)
        if own and own.test_file and own.test_file not in affected_tests:
            affected_tests.append(own.test_file)

        n = len(direct_deps)
        risk = "high" if n >= 2 else ("medium" if n == 1 else "low")

        impact[path] = ChangeImpact(
            direct_dependents=direct_deps,
            affected_tests=affected_tests,
            risk=risk,
        )

    return impact


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def _compute_stats(files: dict[str, FileIndex]) -> dict[str, int]:
    total_files = len(files)
    total_lines = sum(f.line_count for f in files.values())
    tested = sum(1 for f in files.values() if f.has_tests)
    coverage_pct = round(100 * tested / total_files) if total_files else 0

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "tested_files": tested,
        "coverage_pct": coverage_pct,
    }


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def _write_codebase_dir(index: CodebaseIndex, output_dir: Path) -> list[Path]:
    """Write the four ``.handover/codebase/`` files."""
    codebase_dir = output_dir / ".handover" / "codebase"
    codebase_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    # structure.json
    structure = {
        "schema_version": index.schema_version,
        "indexed_at": index.indexed_at,
        "root": index.root,
        "files": {path: asdict(fi) for path, fi in index.files.items()},
    }
    p = codebase_dir / "structure.json"
    p.write_text(json.dumps(structure, indent=2) + "\n", encoding="utf-8")
    written.append(p)

    # symbols.json
    symbols_data = {
        "schema_version": index.schema_version,
        "indexed_at": index.indexed_at,
        "symbols": [asdict(s) for s in index.symbols],
    }
    p = codebase_dir / "symbols.json"
    p.write_text(json.dumps(symbols_data, indent=2) + "\n", encoding="utf-8")
    written.append(p)

    # dependencies.json
    deps_data = {
        "schema_version": index.schema_version,
        "indexed_at": index.indexed_at,
        "graph": {path: asdict(node) for path, node in index.dependency_graph.items()},
        "change_impact": {path: asdict(ci) for path, ci in index.change_impact.items()},
    }
    p = codebase_dir / "dependencies.json"
    p.write_text(json.dumps(deps_data, indent=2) + "\n", encoding="utf-8")
    written.append(p)

    # index.md (rendered from Jinja2 template)
    index_md = _render_index_md(index)
    p = codebase_dir / "index.md"
    p.write_text(index_md, encoding="utf-8")
    written.append(p)

    return written


def _render_index_md(index: CodebaseIndex) -> str:
    """Render the human-readable ``index.md`` from the Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("codebase_index_md.j2")
    return template.render(index=index)

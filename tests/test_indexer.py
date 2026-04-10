"""
Tests for handover/indexer.py and handover/indexers/ — v1.1.2 Codebase Indexer.

Tests verify:
  - Python indexer: function/class extraction, import classification, docstrings
  - TypeScript indexer: export/import regex extraction
  - Generic indexer: fallback line-count-only
  - File discovery: excluded dirs, max lines, exclude globs
  - Dependency graph: inversion, change impact, risk levels
  - index_project: end-to-end write, dry-run, empty-project branch
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.indexer import (
    _build_dependency_graph,
    _compute_change_impact,
    index_project,
)
from handover.indexers import get_all_source_files
from handover.indexers.generic_indexer import GenericIndexer
from handover.indexers.python_indexer import PythonIndexer
from handover.indexers.typescript_indexer import TypeScriptIndexer
from handover.models import FileIndex

FIXTURES = Path(__file__).parent / "fixtures" / "sample_python_project"


# ---------------------------------------------------------------------------
# Python indexer
# ---------------------------------------------------------------------------


class TestPythonIndexer:
    def test_extracts_functions_and_classes(self, tmp_path: Path) -> None:
        src = tmp_path / "example.py"
        src.write_text(
            '"""Module doc."""\n\n'
            "def hello(name: str) -> str:\n"
            '    """Greet someone."""\n'
            '    return f"hi {name}"\n\n'
            "class Greeter:\n"
            '    """A greeter class."""\n'
            "    pass\n",
            encoding="utf-8",
        )
        indexer = PythonIndexer()
        fi, symbols = indexer.index_file(src, tmp_path, {src})

        assert fi.path == "example.py"
        assert "hello" in fi.exports
        assert "Greeter" in fi.exports
        assert len(symbols) == 2
        func_sym = [s for s in symbols if s.name == "hello"][0]
        assert func_sym.type == "function"
        assert "name: str" in func_sym.signature
        assert func_sym.docstring == "Greet someone."
        cls_sym = [s for s in symbols if s.name == "Greeter"][0]
        assert cls_sym.type == "class"

    def test_extracts_internal_vs_external_imports(self, tmp_path: Path) -> None:
        mod_a = tmp_path / "mod_a.py"
        mod_b = tmp_path / "mod_b.py"
        mod_a.write_text("import os\nimport mod_b\n", encoding="utf-8")
        mod_b.write_text("x = 1\n", encoding="utf-8")

        indexer = PythonIndexer()
        fi, _ = indexer.index_file(mod_a, tmp_path, {mod_a, mod_b})

        assert "mod_b" in fi.imports_internal
        assert "os" in fi.imports_external

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.py"
        bad.write_text("def broken(:\n", encoding="utf-8")

        indexer = PythonIndexer()
        fi, symbols = indexer.index_file(bad, tmp_path, {bad})

        assert fi.purpose == "(parse error)"
        assert symbols == []

    def test_extracts_module_docstring_purpose(self, tmp_path: Path) -> None:
        src = tmp_path / "documented.py"
        src.write_text('"""This is the module purpose."""\nx = 1\n', encoding="utf-8")

        indexer = PythonIndexer()
        fi, _ = indexer.index_file(src, tmp_path, {src})

        assert fi.purpose == "This is the module purpose."

    def test_relative_imports_are_internal(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        a = pkg / "a.py"
        b = pkg / "b.py"
        a.write_text("from .b import something\n", encoding="utf-8")
        b.write_text("something = 1\n", encoding="utf-8")

        indexer = PythonIndexer()
        fi, _ = indexer.index_file(a, tmp_path, {a, b, pkg / "__init__.py"})

        # At minimum the relative import should be in imports_internal
        assert any("b" in imp for imp in fi.imports_internal)


# ---------------------------------------------------------------------------
# TypeScript indexer
# ---------------------------------------------------------------------------


class TestTypeScriptIndexer:
    def test_extracts_exports(self, tmp_path: Path) -> None:
        ts = tmp_path / "utils.ts"
        ts.write_text(
            "export function greet(name: string): string {\n"
            '  return `hi ${name}`;\n'
            "}\n\n"
            "export class Logger {\n"
            "  log(msg: string) {}\n"
            "}\n\n"
            "export const VERSION = '1.0';\n",
            encoding="utf-8",
        )
        indexer = TypeScriptIndexer()
        fi, symbols = indexer.index_file(ts, tmp_path, set())

        assert "greet" in fi.exports
        assert "Logger" in fi.exports
        assert "VERSION" in fi.exports
        assert len(symbols) == 3

    def test_classifies_relative_imports_as_internal(self, tmp_path: Path) -> None:
        ts = tmp_path / "main.ts"
        ts.write_text(
            "import { greet } from './utils';\n"
            "import express from 'express';\n",
            encoding="utf-8",
        )
        indexer = TypeScriptIndexer()
        fi, _ = indexer.index_file(ts, tmp_path, set())

        assert "./utils" in fi.imports_internal
        assert "express" in fi.imports_external


# ---------------------------------------------------------------------------
# Generic indexer
# ---------------------------------------------------------------------------


class TestGenericIndexer:
    def test_returns_empty_symbols(self, tmp_path: Path) -> None:
        txt = tmp_path / "readme.txt"
        txt.write_text("hello world\nsecond line\n", encoding="utf-8")

        indexer = GenericIndexer()
        assert indexer.can_index(txt)

        fi, symbols = indexer.index_file(txt, tmp_path, set())
        assert fi.path == "readme.txt"
        assert fi.exports == []
        assert symbols == []
        assert fi.line_count > 0


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


class TestGetAllSourceFiles:
    def test_skips_excluded_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "pkg.js").write_text("x = 1\n", encoding="utf-8")
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "lib.py").write_text("x = 1\n", encoding="utf-8")

        files = get_all_source_files(tmp_path)
        paths = {str(f.relative_to(tmp_path)) for f in files}

        assert "src/app.py" in paths
        assert "node_modules/pkg.js" not in paths
        assert ".venv/lib.py" not in paths

    def test_skips_files_over_500_lines(self, tmp_path: Path) -> None:
        small = tmp_path / "small.py"
        small.write_text("x = 1\n" * 10, encoding="utf-8")
        big = tmp_path / "big.py"
        big.write_text("x = 1\n" * 501, encoding="utf-8")

        files = get_all_source_files(tmp_path)
        names = {f.name for f in files}

        assert "small.py" in names
        assert "big.py" not in names

    def test_honors_exclude_glob(self, tmp_path: Path) -> None:
        (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "skip.generated.py").write_text("x = 1\n", encoding="utf-8")

        files = get_all_source_files(tmp_path, exclude_globs=("*.generated.py",))
        names = {f.name for f in files}

        assert "keep.py" in names
        assert "skip.generated.py" not in names

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        txt = tmp_path / "text.py"
        txt.write_text("x = 1\n", encoding="utf-8")
        binary = tmp_path / "image.bin"
        binary.write_bytes(b"\x00\x01\x02\x03")

        files = get_all_source_files(tmp_path)
        names = {f.name for f in files}

        assert "text.py" in names
        assert "image.bin" not in names


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


class TestDependencyGraph:
    def test_inverts_imports_correctly(self) -> None:
        files = {
            "a.py": FileIndex(
                path="a.py",
                purpose="A",
                imports_internal=["b.py"],
            ),
            "b.py": FileIndex(
                path="b.py",
                purpose="B",
                imports_internal=[],
            ),
            "c.py": FileIndex(
                path="c.py",
                purpose="C",
                imports_internal=["b.py"],
            ),
        }
        graph = _build_dependency_graph(files)

        assert "b.py" in graph["a.py"].depends_on
        assert "a.py" in graph["b.py"].depended_on_by
        assert "c.py" in graph["b.py"].depended_on_by
        assert graph["c.py"].depended_on_by == []

    def test_change_impact_high_when_two_dependents(self) -> None:
        files = {
            "core.py": FileIndex(path="core.py", purpose="Core"),
            "a.py": FileIndex(
                path="a.py",
                purpose="A",
                imports_internal=["core.py"],
            ),
            "b.py": FileIndex(
                path="b.py",
                purpose="B",
                imports_internal=["core.py"],
            ),
        }
        graph = _build_dependency_graph(files)
        impact = _compute_change_impact(graph, files)

        assert impact["core.py"].risk == "high"
        assert len(impact["core.py"].direct_dependents) == 2

    def test_change_impact_low_when_no_dependents(self) -> None:
        files = {
            "leaf.py": FileIndex(path="leaf.py", purpose="Leaf"),
        }
        graph = _build_dependency_graph(files)
        impact = _compute_change_impact(graph, files)

        assert impact["leaf.py"].risk == "low"
        assert impact["leaf.py"].direct_dependents == []


# ---------------------------------------------------------------------------
# index_project end-to-end
# ---------------------------------------------------------------------------


class TestIndexProject:
    def test_returns_none_when_no_source_files(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = index_project(empty)
        assert result is None

    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        result = index_project(tmp_path, dry_run=True)

        assert result is not None
        assert result.stats["total_files"] == 1
        assert not (tmp_path / ".handover" / "codebase").exists()

    def test_writes_four_files_under_codebase_dir(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text(
            '"""App entry."""\ndef main(): pass\n',
            encoding="utf-8",
        )
        result = index_project(tmp_path)
        assert result is not None

        codebase = tmp_path / ".handover" / "codebase"
        assert (codebase / "structure.json").exists()
        assert (codebase / "symbols.json").exists()
        assert (codebase / "dependencies.json").exists()
        assert (codebase / "index.md").exists()

    def test_structure_json_is_valid_and_contains_expected_keys(self, tmp_path: Path) -> None:
        (tmp_path / "hello.py").write_text(
            '"""Hello module."""\ndef greet(): pass\n',
            encoding="utf-8",
        )
        index_project(tmp_path)

        data = json.loads(
            (tmp_path / ".handover" / "codebase" / "structure.json").read_text(encoding="utf-8")
        )
        assert data["schema_version"] == "1.0"
        assert "hello.py" in data["files"]
        assert data["files"]["hello.py"]["purpose"] == "Hello module."

    def test_index_md_renders_where_to_find_table(self, tmp_path: Path) -> None:
        (tmp_path / "utils.py").write_text(
            '"""Utility functions."""\ndef helper(): pass\n',
            encoding="utf-8",
        )
        index_project(tmp_path)

        md = (tmp_path / ".handover" / "codebase" / "index.md").read_text(encoding="utf-8")
        assert "Where to find things" in md
        assert "utils.py" in md

    def test_index_md_lists_high_risk_files(self, tmp_path: Path) -> None:
        # core.py is imported by a.py and b.py → high risk
        (tmp_path / "core.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "a.py").write_text("import core\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("import core\n", encoding="utf-8")

        index_project(tmp_path)

        md = (tmp_path / ".handover" / "codebase" / "index.md").read_text(encoding="utf-8")
        assert "High-risk files" in md
        assert "core.py" in md

    def test_fixture_project_indexes_correctly(self) -> None:
        """End-to-end test using the sample_python_project fixture."""
        if not FIXTURES.exists():
            return  # Skip if fixture not present

        # Use a temp output to avoid polluting fixtures
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            # Copy fixture to tmp so we don't write .handover/ inside fixtures
            import shutil

            project = Path(td) / "project"
            shutil.copytree(FIXTURES, project)

            result = index_project(project)
            assert result is not None
            assert result.stats["total_files"] >= 3  # auth, models, database + __init__

            # auth.py should have exports
            auth_files = [
                p for p in result.files if p.endswith("auth.py") and "test" not in p
            ]
            assert len(auth_files) >= 1
            auth = result.files[auth_files[0]]
            assert "create_token" in auth.exports
            assert "AuthMiddleware" in auth.exports

            # Check that 4 files were written
            codebase = project / ".handover" / "codebase"
            assert (codebase / "structure.json").exists()
            assert (codebase / "symbols.json").exists()
            assert (codebase / "dependencies.json").exists()
            assert (codebase / "index.md").exists()

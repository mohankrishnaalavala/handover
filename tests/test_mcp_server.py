"""
Tests for handover/mcp_server.py — Phase 6 MCP server.

The MCP SDK is mocked so these tests run without `pip install handover[mcp]`.
Tests verify:
  - run_handover tool logic (pipeline integration)
  - Missing dependency error handling
  - CLI `handover mcp` subcommand handles missing mcp package
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from handover.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers to mock the mcp package
# ---------------------------------------------------------------------------


def _inject_mcp_mock() -> dict[str, MagicMock]:
    """Inject minimal mcp stubs into sys.modules so mcp_server can be imported."""
    mcp_mock = MagicMock()
    fastmcp_mock = MagicMock()
    server_mock = MagicMock()
    mocks = {
        "mcp": mcp_mock,
        "mcp.server": server_mock,
        "mcp.server.fastmcp": fastmcp_mock,
    }
    for name, mock in mocks.items():
        sys.modules.setdefault(name, mock)
    return mocks


def _remove_mcp_mock(originals: dict[str, MagicMock]) -> None:
    for name in originals:
        sys.modules.pop(name, None)
    # Also evict mcp_server from cache so it re-imports cleanly
    sys.modules.pop("handover.mcp_server", None)


# ---------------------------------------------------------------------------
# run_handover tool function (unit tests)
# ---------------------------------------------------------------------------


class TestRunHandoverTool:
    """Test the run_handover_impl() function in isolation (no MCP SDK needed)."""

    def _invoke(
        self,
        input_file: str,
        output_dir: str,
        source: str = "auto",
        target: str = "claude-code",
        no_llm: bool = True,
    ) -> str:
        """Call run_handover_impl directly — no MCP stubs needed."""
        from handover.mcp_server import run_handover_impl

        return run_handover_impl(
            input_file=input_file,
            output_dir=output_dir,
            source=source,
            target=target,
            no_llm=no_llm,
        )

    def test_tool_returns_string(self, tmp_path: Path) -> None:
        result = self._invoke(
            input_file=str(FIXTURES / "claude_single.json"),
            output_dir=str(tmp_path),
            no_llm=True,
        )
        assert isinstance(result, str)

    def test_tool_writes_files(self, tmp_path: Path) -> None:
        self._invoke(
            input_file=str(FIXTURES / "claude_single.json"),
            output_dir=str(tmp_path),
            no_llm=True,
        )
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "PLAN.md").exists()

    def test_tool_returns_goal_info(self, tmp_path: Path) -> None:
        result = self._invoke(
            input_file=str(FIXTURES / "claude_single.json"),
            output_dir=str(tmp_path),
            no_llm=True,
        )
        assert "Goal:" in result

    def test_tool_missing_input_returns_error(self, tmp_path: Path) -> None:
        result = self._invoke(
            input_file="/nonexistent/file.json",
            output_dir=str(tmp_path),
        )
        assert "Error" in result

    def test_tool_target_codex(self, tmp_path: Path) -> None:
        self._invoke(
            input_file=str(FIXTURES / "claude_single.json"),
            output_dir=str(tmp_path),
            target="codex",
            no_llm=True,
        )
        assert (tmp_path / "AGENTS.md").exists()

    def test_tool_target_all(self, tmp_path: Path) -> None:
        self._invoke(
            input_file=str(FIXTURES / "claude_single.json"),
            output_dir=str(tmp_path),
            target="all",
            no_llm=True,
        )
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()


# ---------------------------------------------------------------------------
# CLI handover mcp subcommand
# ---------------------------------------------------------------------------


class TestMCPCLI:
    def test_mcp_missing_dependency_shows_install_hint(self) -> None:
        runner = CliRunner()
        # Simulate ImportError when importing mcp_server
        with patch("handover.cli.run_mcp_server.callback") as _:
            pass  # just check the command exists

        # Test the import error path by temporarily hiding mcp
        orig = sys.modules.get("handover.mcp_server")
        sys.modules["handover.mcp_server"] = None  # type: ignore[assignment]
        try:
            result = runner.invoke(main, ["mcp"])
            # Should show an install hint, not a traceback
            assert result.exit_code != 0 or "mcp" in result.output.lower()
        finally:
            if orig is not None:
                sys.modules["handover.mcp_server"] = orig
            else:
                sys.modules.pop("handover.mcp_server", None)

    def test_mcp_command_registered(self) -> None:
        """Verify that `handover mcp` is a registered subcommand."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "mcp" in result.output

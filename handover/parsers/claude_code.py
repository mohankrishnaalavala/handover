"""
handover/parsers/claude_code.py

Parser for Claude Code session logs stored at:
  ~/.claude/projects/<project-hash>/<session-id>.jsonl

Each line is a JSON record with type "user", "assistant", or housekeeping types
(queue-operation, file-history-snapshot, etc.) which are skipped.

The project hash is derived by replacing all "/" in the absolute project path
with "-":  /Users/alice/projects/myapp  →  -Users-alice-projects-myapp

parse()          — returns ConversationMessage list (for summarizer compatibility)
parse_session_entries()  — returns raw session dicts (for reverse pipeline)
discover_sessions()  — lists all sessions for a given project directory
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.models import ConversationMessage, SessionMeta
from handover.parsers.base import BaseParser

# Tool names whose inputs reference files we want to track
_FILE_TOOLS = frozenset({"Edit", "Write", "NotebookEdit", "MultiEdit"})

# Claude context window capacity (tokens) for usage estimation
_CONTEXT_WINDOW_TOKENS = 200_000


class ClaudeCodeSessionParser(BaseParser):
    """
    Reads Claude Code session JSONL files from ~/.claude/projects/.

    The JSONL format has one JSON record per line.  Only "user" and
    "assistant" typed records are converted to ConversationMessage;
    all other types (queue-operation, file-history-snapshot, …) are skipped.
    """

    source_name = "claude-code"

    # ------------------------------------------------------------------
    # BaseParser interface
    # ------------------------------------------------------------------

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Convert a session JSONL file into a flat list of ConversationMessages.

        Skips thinking blocks and tool_result-only user turns (no text content).
        This output is suitable for feeding into the summarizer.

        Args:
            file_path: Absolute path to a Claude Code session .jsonl file.

        Returns:
            List of ConversationMessage objects in chronological order.
        """
        messages: list[ConversationMessage] = []
        for entry in self.parse_session_entries(file_path):
            msg = self._entry_to_message(entry)
            if msg is not None:
                messages.append(msg)
        return messages

    def detect_format_version(self, file_path: Path) -> str:
        """Return the Claude Code version from the first user entry, or 'unknown'."""
        for entry in self.parse_session_entries(file_path):
            if entry.get("type") == "user":
                return str(entry.get("version", "unknown"))
        return "unknown"

    def list_conversations(self, path: Path) -> list[dict[str, str]]:
        """
        Treat each .jsonl file in a projects directory as a 'conversation'.

        If *path* is a directory, list all .jsonl files inside it.
        If *path* is a file, return a single-item list for that session.
        """
        if path.is_dir():
            sessions = self.discover_sessions(path)
        else:
            sessions = self.discover_sessions(path.parent)

        return [
            {
                "id": s.session_id,
                "title": f"Session {s.session_id[:8]} @ {s.started_at[:10]}",
                "date": s.started_at,
            }
            for s in sessions
        ]

    def parse_by_id(self, path: Path, conversation_id: str) -> list[ConversationMessage]:
        """Parse a session by its ID from a projects directory."""
        session_file = path / f"{conversation_id}.jsonl" if path.is_dir() else path
        return self.parse(session_file)

    # ------------------------------------------------------------------
    # Phase 4 extensions
    # ------------------------------------------------------------------

    def parse_session_entries(self, file_path: Path) -> list[dict]:  # type: ignore[type-arg]
        """
        Read all message-type entries from a session JSONL file.

        Returns only "user" and "assistant" typed records.
        Housekeeping records (queue-operation, file-history-snapshot, etc.) are dropped.

        Args:
            file_path: Path to the session .jsonl file.

        Returns:
            List of raw dicts, one per message, in file order.
        """
        entries: list[dict] = []  # type: ignore[type-arg]
        try:
            text = file_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Session file not found: {file_path}") from exc

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") in ("user", "assistant"):
                entries.append(record)

        return entries

    def discover_sessions(self, project_dir: Path | None = None) -> list[SessionMeta]:
        """
        List all Claude Code sessions for a given project directory.

        Args:
            project_dir: Absolute path to the project root (defaults to cwd).
                         The function derives the Claude projects hash from this path.

        Returns:
            List of SessionMeta sorted by most recent first.
        """
        target = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        projects_root = Path.home() / ".claude" / "projects"
        project_hash = self.project_hash(target)
        sessions_dir = projects_root / project_hash

        if not sessions_dir.exists():
            return []

        metas: list[SessionMeta] = []
        for jsonl_file in sorted(sessions_dir.glob("*.jsonl")):
            meta = self._read_session_meta(jsonl_file)
            if meta is not None:
                metas.append(meta)

        return sorted(metas, key=lambda m: m.started_at, reverse=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def project_hash(project_path: Path) -> str:
        """
        Derive the Claude Code projects directory name for a given path.

        Claude Code names its per-project directory by replacing every "/"
        in the absolute path with "-":
          /Users/alice/projects/myapp  →  -Users-alice-projects-myapp

        Args:
            project_path: Absolute path to the project root.

        Returns:
            Directory name used by Claude Code under ~/.claude/projects/.
        """
        return str(project_path).replace("/", "-")

    def _read_session_meta(self, jsonl_file: Path) -> SessionMeta | None:
        """Extract lightweight metadata from a session file without reading it fully."""
        try:
            text = jsonl_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        session_id = jsonl_file.stem
        started_at = ""
        git_branch = ""
        project_path = ""
        message_count = 0

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("type") not in ("user", "assistant"):
                continue

            message_count += 1

            if not started_at and record.get("type") == "user":
                started_at = record.get("timestamp", "")
                git_branch = record.get("gitBranch", "")
                project_path = record.get("cwd", "")

        if not started_at:
            return None

        return SessionMeta(
            session_id=session_id,
            project_path=project_path,
            file_path=jsonl_file,
            started_at=started_at,
            git_branch=git_branch,
            message_count=message_count,
            size_bytes=jsonl_file.stat().st_size,
        )

    def _entry_to_message(self, entry: dict) -> ConversationMessage | None:  # type: ignore[type-arg]
        """Convert a raw session entry to a ConversationMessage, or None if not text."""
        entry_type = entry.get("type")
        message = entry.get("message", {})
        content_raw = message.get("content", "")
        timestamp = entry.get("timestamp")

        if entry_type == "user":
            # content can be a plain string or a list of blocks
            if isinstance(content_raw, str):
                text = content_raw.strip()
            else:
                # List of blocks — extract text blocks, skip tool_result
                text = " ".join(
                    block.get("text", "")
                    for block in content_raw
                    if isinstance(block, dict) and block.get("type") == "text"
                ).strip()

            if not text:
                return None  # tool_result-only turn — skip

            return ConversationMessage(role="user", content=text, timestamp=timestamp)

        if entry_type == "assistant":
            if isinstance(content_raw, list):
                # Concatenate all text blocks; skip thinking and tool_use
                text = "\n\n".join(
                    block.get("text", "")
                    for block in content_raw
                    if isinstance(block, dict) and block.get("type") == "text"
                ).strip()
            else:
                text = str(content_raw).strip()

            if not text:
                return None  # tool-use-only turn — skip

            return ConversationMessage(role="assistant", content=text, timestamp=timestamp)

        return None

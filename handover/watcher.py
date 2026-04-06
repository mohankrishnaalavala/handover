"""
handover/watcher.py

File-system watcher for `handover watch`.

Monitors ~/.claude/projects/<hash>/ for new Claude Code session files.
When a session .jsonl file has been idle for `idle_seconds` it triggers
the reverse pipeline and writes HANDOVER.md to the output directory.

Requires the optional `watchdog` dependency:
  pip install handover[watch]
"""

from __future__ import annotations

import threading
from pathlib import Path

from handover.parsers.claude_code import ClaudeCodeSessionParser


class _SessionEventHandler:
    """
    Debounced session file handler.

    Schedules a processing timer on each file-modification event.
    If the file is modified again before the timer fires, the timer resets.
    """

    def __init__(
        self,
        output_dir: Path,
        no_llm: bool,
        idle_seconds: int,
    ) -> None:
        self._output_dir = output_dir
        self._no_llm = no_llm
        self._idle_seconds = idle_seconds
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_created(self, src_path: str) -> None:
        """New session file appeared — start idle timer."""
        self._schedule(src_path)

    def on_modified(self, src_path: str) -> None:
        """Session file still being written — reset idle timer."""
        self._schedule(src_path)

    def _schedule(self, src_path: str) -> None:
        if not src_path.endswith(".jsonl"):
            return
        with self._lock:
            existing = self._timers.get(src_path)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self._idle_seconds, self._process, args=[src_path])
            timer.daemon = True
            timer.start()
            self._timers[src_path] = timer

    def _process(self, src_path: str) -> None:
        """Idle timeout reached — run the reverse pipeline."""
        with self._lock:
            self._timers.pop(src_path, None)

        session_file = Path(src_path)
        if not session_file.exists():
            return

        print(f"[handover watch] Processing session: {session_file.name}")
        try:
            from handover.generator import Generator
            from handover.reverse import reverse

            context = reverse(
                session_file=session_file,
                project_dir=self._output_dir,
                use_llm=not self._no_llm,
            )
            gen = Generator()
            gen.generate_handover(context, self._output_dir, dry_run=False)
            print(
                f"[handover watch] Wrote HANDOVER.md to {self._output_dir}/"
                f"  ({len(context.files_changed)} files changed)"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[handover watch] Error processing {session_file.name}: {exc}")


def start_watching(
    project_dir: Path,
    output_dir: Path,
    no_llm: bool,
    idle_seconds: int,
) -> None:
    """
    Block and watch for Claude Code sessions until Ctrl-C.

    Args:
        project_dir: The project root — used to derive the Claude projects hash.
        output_dir: Where to write HANDOVER.md after each session.
        no_llm: If True, skip LLM calls (heuristics only).
        idle_seconds: Seconds of inactivity before processing a session file.
    """
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    sessions_root = (
        Path.home() / ".claude" / "projects" / ClaudeCodeSessionParser.project_hash(project_dir)
    )
    sessions_root.mkdir(parents=True, exist_ok=True)

    debouncer = _SessionEventHandler(
        output_dir=output_dir,
        no_llm=no_llm,
        idle_seconds=idle_seconds,
    )

    class _Adapter(FileSystemEventHandler):
        def on_created(self, event: object) -> None:
            if not getattr(event, "is_directory", False):
                debouncer.on_created(getattr(event, "src_path", ""))

        def on_modified(self, event: object) -> None:
            if not getattr(event, "is_directory", False):
                debouncer.on_modified(getattr(event, "src_path", ""))

    observer = Observer()
    observer.schedule(_Adapter(), str(sessions_root), recursive=False)
    observer.start()
    print(f"[handover watch] Monitoring: {sessions_root}")
    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

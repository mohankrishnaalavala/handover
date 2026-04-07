# Adding a Target Adapter

Target adapters let handover generate output for any terminal coding agent from the same `HandoverContext`. This guide walks you through adding a new target in three steps.

`handover` follows a simple principle: **shared semantic extraction, target-specific artifact generation**. The parser and summarizer extract goal, tasks, decisions, and constraints once. Each target adapter decides how to express that context for its coding agent — including which filenames to use, how many files to emit, and what format each file takes.

## Overview

Targets live in `handover/targets/`. Each adapter subclasses `BaseTarget` and is registered in `TARGET_REGISTRY`. The `--target` CLI flag selects which adapter to use, and its choices are derived dynamically from the registry — adding a new target here automatically makes it available in the CLI.

```
handover/targets/
├── __init__.py       # registry + get_target() / list_targets()
├── base.py           # BaseTarget abstract class
├── claude_code.py    # Claude Code: CLAUDE.md + PLAN.md
├── codex.py          # Codex CLI: AGENTS.md + TASKS.md
├── copilot.py        # GitHub Copilot: .github/copilot-instructions.md
├── aider.py          # aider: .aider.conf.yml
└── goose.py          # Goose: goose-context.json
```

---

## Step 1 — Create the adapter

Create `handover/targets/<your_agent>.py`:

```python
from __future__ import annotations

from pathlib import Path

from handover.models import HandoverContext
from handover.targets.base import BaseTarget


class YourAgentTarget(BaseTarget):
    """Generates <output-file> for YourAgent."""

    @property
    def name(self) -> str:
        """Identifier used in --target flag."""
        return "your-agent"

    def generate(
        self,
        context: HandoverContext,
        output_dir: Path,
        dry_run: bool = False,
    ) -> list[Path]:
        """
        Generate your-agent context file from HandoverContext.

        Returns:
            [output_dir/<output-file>]
        """
        output_path = output_dir / "your-agent-context.md"
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(self._render(context), encoding="utf-8")
        return [output_path]

    def _render(self, context: HandoverContext) -> str:
        """Build the file content from the HandoverContext."""
        lines = [f"# {context.goal}", ""]
        for task in context.tasks:
            lines.append(f"- [ ] {task.title}")
        return "\n".join(lines) + "\n"
```

**Rules:**
- Use stdlib only (no new `dependencies` in `pyproject.toml`). JSON → `json.dumps`, YAML → string template.
- Type hints required on all public methods.
- Docstrings required on all public methods.
- Return `[output_path]` (or multiple paths) in both dry_run and non-dry_run cases. Only skip writing when `dry_run=True`.
- If your target writes into a subdirectory (e.g. `.github/`), create it inside `output_dir` — the returned paths must be absolute (under `output_dir`).

### Optional: override `describe()`

`BaseTarget` provides a default `describe()` that returns `{"name": self.name, "description": ""}`. Override it to give users richer introspection:

```python
def describe(self) -> dict[str, str]:
    return {
        "name": "your-agent",
        "description": "YourAgent — generates your-agent-context.md",
    }
```

### Multi-file targets

A target can generate any number of files. Just return all paths from `generate()`:

```python
def generate(self, context, output_dir, dry_run=False):
    file_a = output_dir / "SPEC.md"
    file_b = output_dir / "TASKS.md"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_a.write_text(self._render_spec(context), encoding="utf-8")
        file_b.write_text(self._render_tasks(context), encoding="utf-8")
    return [file_a, file_b]
```

---

## Step 2 — Register it

Add your adapter to `handover/targets/__init__.py`:

```python
from handover.targets.your_agent import YourAgentTarget  # add this

TARGET_REGISTRY: dict[str, type[BaseTarget]] = {
    "claude-code": ClaudeCodeTarget,
    "codex": CodexTarget,
    "aider": AiderTarget,
    "goose": GooseTarget,
    "copilot": CopilotTarget,
    "your-agent": YourAgentTarget,  # add this
}
```

The `--target` CLI flag and `--target all` pick up all registered entries automatically.

---

## Step 3 — Write tests

Add a test class to `tests/test_targets.py`:

```python
class TestYourAgentTarget:
    def test_generates_output_file(self, tmp_path: Path) -> None:
        t = YourAgentTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / "your-agent-context.md").exists()

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        t = YourAgentTarget()
        t.generate(make_context(), tmp_path, dry_run=True)
        assert not (tmp_path / "your-agent-context.md").exists()

    def test_dry_run_returns_path(self, tmp_path: Path) -> None:
        t = YourAgentTarget()
        paths = t.generate(make_context(), tmp_path, dry_run=True)
        assert paths[0].name == "your-agent-context.md"

    def test_content_contains_goal(self, tmp_path: Path) -> None:
        t = YourAgentTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "your-agent-context.md").read_text()
        assert "FastAPI REST API" in content

    def test_name_property(self) -> None:
        assert YourAgentTarget().name == "your-agent"
```

Run the full suite to ensure coverage stays above 80 %:

```bash
pytest tests/ -v --cov=handover --cov-fail-under=80
```

---

## HandoverContext fields

Your `_render()` has access to the full `HandoverContext`:

| Field | Type | Description |
|-------|------|-------------|
| `goal` | `str` | High-level project goal |
| `tech_stack` | `dict[str, str]` | e.g. `{"language": "Python", "framework": "FastAPI"}` |
| `decisions` | `list[Decision]` | Each has `.topic`, `.decision`, `.rationale` |
| `tasks` | `list[Task]` | Each has `.title`, `.description`, `.priority`, `.done` |
| `constraints` | `list[str]` | Hard constraints |
| `non_goals` | `list[str]` | Explicitly out of scope |
| `open_questions` | `list[str]` | Unresolved questions |

See `handover/models.py` for the full dataclass definitions.

---

## Testing your target via CLI

```bash
handover --input chat.json --output /tmp/out --target your-agent --no-llm
handover --input chat.json --output /tmp/out --target all --no-llm
```

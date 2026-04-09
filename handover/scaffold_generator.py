"""
handover/scaffold_generator.py

v1.1.0 — writes the per-target `.claude/` workspace.

Reads a `ScaffoldContext` and produces:

```
.claude/
├── agents/<name>.md       (one per detected domain)
├── skills/<name>.md       (one per skill attached to a detected domain)
├── commands/<name>.md     (one per default command)
├── hooks/<name>           (executable script per hook)
└── settings.json          (wires hooks into Claude Code)
```

This is currently invoked by `targets/claude_code.py`. Other targets do not
generate a `.claude/` directory (their format is owned by their own target
file). Loose-coupling: the only public surface is
`generate_claude_workspace()`.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from handover import __version__
from handover.models import ScaffoldContext

DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"


class ClaudeWorkspaceExistsError(FileExistsError):
    """Raised when `.claude/` already exists and `overwrite` is False."""


def generate_claude_workspace(
    scaffold: ScaffoldContext,
    output_dir: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """
    Render and write the `.claude/` workspace.

    Args:
        scaffold: The `ScaffoldContext` produced by `scaffold_extractor`.
        output_dir: Project root. The function writes into
            ``output_dir/.claude/``.
        overwrite: When False (default), raise `ClaudeWorkspaceExistsError`
            if ``output_dir/.claude/`` already exists.
        dry_run: When True, do not touch the filesystem; return the list of
            paths that would be written.

    Returns:
        A list of `Path` objects covering every agent, skill, command,
        hook, and the `settings.json` file.

    Raises:
        ClaudeWorkspaceExistsError: If `.claude/` already exists and
            `overwrite=False`.
    """
    claude_root = output_dir / ".claude"

    if not dry_run and claude_root.exists() and not overwrite:
        raise ClaudeWorkspaceExistsError(
            f".claude/ already exists at {claude_root}. "
            "Pass --overwrite-handover-dir to replace it."
        )

    env = _make_env()
    written: list[Path] = []

    written.extend(_write_collection(env, claude_root, "agents", scaffold, dry_run))
    written.extend(_write_collection(env, claude_root, "skills", scaffold, dry_run))
    written.extend(_write_collection(env, claude_root, "commands", scaffold, dry_run))
    written.extend(_write_hooks(env, claude_root, scaffold, dry_run))

    settings_path = claude_root / "settings.json"
    if not dry_run:
        claude_root.mkdir(parents=True, exist_ok=True)
        rendered = env.get_template("settings_json.j2").render(
            scaffold=scaffold,
            version=__version__,
        )
        settings_path.write_text(rendered, encoding="utf-8")
    written.append(settings_path)

    return written


# ---------------------------------------------------------------------------
# Collection writers
# ---------------------------------------------------------------------------


def _write_collection(
    env: Environment,
    claude_root: Path,
    kind: str,
    scaffold: ScaffoldContext,
    dry_run: bool,
) -> list[Path]:
    """
    Write `.claude/<kind>/<name>.md` for each item in the matching list.

    `kind` is one of "agents", "skills", "commands". The Jinja template
    name is the singular form ("agent.j2", "skill.j2", "command.j2") and
    the loop variable passed to the template uses the same singular form.
    """
    items = getattr(scaffold, kind)
    template_singular = kind.rstrip("s")  # agents -> agent, skills -> skill
    template = env.get_template(f"{template_singular}.j2")
    target_dir = claude_root / kind
    written: list[Path] = []

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for item in items:
        out_path = target_dir / f"{item.name}.md"
        if not dry_run:
            rendered = template.render(
                **{template_singular: item, "scaffold": scaffold, "version": __version__}
            )
            out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)

    return written


def _write_hooks(
    env: Environment,
    claude_root: Path,
    scaffold: ScaffoldContext,
    dry_run: bool,
) -> list[Path]:
    """Write hook scripts and chmod them executable."""
    target_dir = claude_root / "hooks"
    template = env.get_template("hook_pre_tool_use.j2")
    written: list[Path] = []

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for hook in scaffold.hooks:
        out_path = target_dir / hook.name
        if not dry_run:
            rendered = template.render(
                hook=hook,
                scaffold=scaffold,
                version=__version__,
            )
            out_path.write_text(rendered, encoding="utf-8")
            os.chmod(out_path, 0o755)
        written.append(out_path)

    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(DEFAULT_TEMPLATE_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

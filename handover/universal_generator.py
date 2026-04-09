"""
handover/universal_generator.py

v1.1.0 — writes the vendor-neutral `.handover/` knowledge base.

Reads a `ScaffoldContext` and renders 20 files into `<output_dir>/.handover/`:

```
.handover/
├── manifest.yaml
├── context/
│   ├── overview.md, architecture.md, decisions.md,
│   ├── constraints.md, risks.md, acceptance-criteria.md
├── work/
│   ├── spec.md, tasks.md, milestones.md, backlog.json
├── standards/
│   ├── coding-standards.md, testing-standards.md,
│   ├── security-guardrails.md, release-checklist.md
└── prompts/
    ├── implement.md, review.md, debug.md,
    ├── test.md, onboard.md, continue.md
```

Loose-coupling rules:

- All filenames live in `HANDOVER_DIR_FILES` — adding a new scaffold file
  is one row in that list.
- `backlog.json` is the only non-Jinja artefact and is serialized via
  `json.dumps`.
- This module knows nothing about LLMs, click, or HTTP.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from handover import __version__
from handover.models import ScaffoldContext

DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates" / "handover"

# Registry: (template_filename, relative_output_path).
# Adding a new file to `.handover/` is one entry here plus a `.j2` template.
HANDOVER_DIR_FILES: list[tuple[str, str]] = [
    ("manifest_yaml.j2", "manifest.yaml"),
    ("context_overview.j2", "context/overview.md"),
    ("context_architecture.j2", "context/architecture.md"),
    ("context_decisions.j2", "context/decisions.md"),
    ("context_constraints.j2", "context/constraints.md"),
    ("context_risks.j2", "context/risks.md"),
    ("context_acceptance_criteria.j2", "context/acceptance-criteria.md"),
    ("work_spec.j2", "work/spec.md"),
    ("work_tasks.j2", "work/tasks.md"),
    ("work_milestones.j2", "work/milestones.md"),
    ("standards_coding.j2", "standards/coding-standards.md"),
    ("standards_testing.j2", "standards/testing-standards.md"),
    ("standards_security.j2", "standards/security-guardrails.md"),
    ("standards_release.j2", "standards/release-checklist.md"),
    ("prompt_implement.j2", "prompts/implement.md"),
    ("prompt_review.j2", "prompts/review.md"),
    ("prompt_debug.j2", "prompts/debug.md"),
    ("prompt_test.j2", "prompts/test.md"),
    ("prompt_onboard.j2", "prompts/onboard.md"),
    ("prompt_continue.j2", "prompts/continue.md"),
]

_BACKLOG_RELATIVE_PATH = "work/backlog.json"


class HandoverDirExistsError(FileExistsError):
    """Raised when `.handover/` already exists and `overwrite` is False."""


def write_handover_dir(
    scaffold: ScaffoldContext,
    output_dir: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """
    Render and write the entire `.handover/` directory.

    Args:
        scaffold: The `ScaffoldContext` produced by `scaffold_extractor`.
        output_dir: Project root. The function writes into
            ``output_dir/.handover/``.
        overwrite: When False (default), raise `HandoverDirExistsError` if
            ``output_dir/.handover/`` already exists.
        dry_run: When True, do not touch the filesystem; return the list of
            paths that would be written.

    Returns:
        A list of `Path` objects — every file rendered (or that would be
        rendered, in dry-run mode), in registry order followed by
        `backlog.json`.

    Raises:
        HandoverDirExistsError: If `.handover/` already exists and
            `overwrite=False`.
    """
    handover_root = output_dir / ".handover"

    if not dry_run and handover_root.exists() and not overwrite:
        raise HandoverDirExistsError(
            f".handover/ already exists at {handover_root}. "
            "Pass --overwrite-handover-dir to replace it."
        )

    env = _make_env()
    written: list[Path] = []

    for template_name, rel_path in HANDOVER_DIR_FILES:
        out_path = handover_root / rel_path
        if not dry_run:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            template = env.get_template(template_name)
            rendered = template.render(scaffold=scaffold, version=__version__)
            out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)

    backlog_path = handover_root / _BACKLOG_RELATIVE_PATH
    if not dry_run:
        backlog_path.parent.mkdir(parents=True, exist_ok=True)
        backlog_path.write_text(
            json.dumps(asdict(scaffold.backlog), indent=2) + "\n",
            encoding="utf-8",
        )
    written.append(backlog_path)

    return written


def _make_env() -> Environment:
    """Build a Jinja2 environment matching `Generator`'s configuration."""
    return Environment(
        loader=FileSystemLoader(str(DEFAULT_TEMPLATE_DIR)),
        autoescape=select_autoescape([]),  # Markdown output — no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
    )

# Cowork Prompt — handover Project Setup

Paste this prompt into Claude Cowork along with the attached PRD document (handover-prd-v2.md).

---

I'm starting an open-source project called `handover`. The attached PRD is the source of truth for this project. Read it fully before doing anything.

## Pre-flight check (do this first)

Before creating anything, run this in my terminal to check if the PyPI package name `handover` is available:

```bash
pip install handover 2>&1 | head -5
```

- If it says "not found" or "no such package" → use `handover` as the PyPI name
- If it installs something → use `handover-cli` as the PyPI name
- In both cases, the CLI command the user types is always `handover`
- Let me know which name you used before proceeding

## Setup tasks — execute in this exact order

### 1. Create the GitHub repository

```
Name: handover
Description: Universal AI chat to local agent handover tool — Design in chat. Build in terminal. Zero context lost.
Visibility: Public
License: MIT
Initialize with README: No (we'll write our own)
Topics: claude, claude-code, cli, handover, agent, open-source, python
```

### 2. Clone locally

Clone the repo to exactly this path:
```
/Users/mohankrishnaalavala/Documents/project_handover
```

### 3. Create the full folder structure

Create every folder and file from Section 12 of the PRD.
For files not yet written (e.g. source .py files), create them as empty stubs with a single comment:
```python
# TODO: implement - see PRD Section X
```

### 4. Write these files with complete real content

**`CLAUDE.md`**
Use the exact content from Section 13 of the PRD. This is critical — Claude Code reads this file first.

**`PLAN.md`**
Use the full task checklist from Section 15 of the PRD, formatted as GitHub Flavored Markdown checkboxes.

**`LICENSE`**
Full MIT license text:
- Copyright holder: Mohan Krishnaa Alavala
- Year: 2026

**`pyproject.toml`**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "handover-cli"           # or "handover" if available — see pre-flight check
version = "0.1.0"
description = "Universal AI chat to local agent handover tool"
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Mohan Krishnaa Alavala" }]
requires-python = ">=3.11"
keywords = ["claude", "claude-code", "cli", "handover", "agent", "ai"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = [
  "click>=8.0",
  "anthropic>=0.40.0",
  "jinja2>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[project.scripts]
handover = "handover.cli:main"

[project.urls]
Homepage = "https://github.com/mohankrishnaalavala/handover"
Issues = "https://github.com/mohankrishnaalavala/handover/issues"
```

**`README.md`**
Write a complete README including:
- Project name + tagline from PRD Section 1
- Badges: PyPI version, Python versions, License, CI status
- Install section: `pip install handover-cli`
- Quickstart: show the 3 most common CLI commands from PRD Section 11
- This exact `--dry-run` demo block (use the output shown in PRD Section 11):
  ```
  $ handover --input chat.json --dry-run
  (paste the full dry-run output from the PRD)
  ```
- Supported input formats table from PRD Section 9
- Roadmap table from PRD Section 17
- Contributing section: "The primary contribution path is adding a new source adapter. See docs/adding-an-adapter.md."
- Link to full PRD

**`.gitignore`**
Standard Python gitignore (venv, __pycache__, .egg-info, dist, build, .env, .DS_Store, .pytest_cache, .coverage, htmlcov)

**`.github/workflows/ci.yml`**
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/ -v --cov=handover --cov-report=term-missing
```

**`.github/workflows/release.yml`**
GitHub Actions workflow that publishes to PyPI on version tag (v*) using PyPI Trusted Publisher (pypa/gh-action-pypi-publish).

**`.github/ISSUE_TEMPLATE/bug_report.md`**
Standard bug report template with: description, steps to reproduce, expected vs actual, CLI version, Python version, OS.

**`.github/ISSUE_TEMPLATE/feature_request.md`**
Standard feature request template with: problem statement, proposed solution, alternatives considered, phase it belongs to.

**`.github/PULL_REQUEST_TEMPLATE.md`**
PR checklist: [ ] Tests added, [ ] Docs updated, [ ] If new adapter: added-adapter.md guide followed, [ ] PLAN.md updated if tasks completed.

**`CONTRIBUTING.md`**
Include:
- Setup: clone, `pip install -e ".[dev]"`, run tests
- The adapter contribution path: "Adding a new source (ChatGPT, Gemini, etc.) is the primary way to contribute. Each adapter is one class in `handover/parsers/`. See `docs/adding-an-adapter.md` for the step-by-step guide."
- Code standards from CLAUDE.md Section
- How to run tests

**`docs/adding-an-adapter.md`**
Write a complete guide for adding a new source adapter:
1. Create `handover/parsers/{source_name}.py`
2. Subclass `BaseParser` from `parsers/base.py`
3. Implement `parse(file_path) -> list[ConversationMessage]`
4. Register the adapter in `parsers/__init__.py`
5. Add test fixture in `tests/fixtures/`
6. Add format to the supported formats table in README
7. Add source to the `--source` flag in cli.py

**`.claude/commands/add-adapter.md`**
Custom Claude Code command for scaffolding a new adapter:
```
Scaffold a new source adapter for handover.

Source name: $ARGUMENTS

Steps:
1. Create handover/parsers/{source_name}.py with BaseParser subclass
2. Add to parsers/__init__.py registry
3. Create tests/fixtures/{source_name}_sample.json placeholder
4. Add test stub to tests/test_parser.py
5. Update README supported formats table
6. Print next steps for the developer
```

### 5. Create empty stub files for all source files

For each `.py` file in `handover/` that doesn't have content above, create it with:
- Module docstring explaining its purpose (1-2 lines referencing the PRD section)
- A `# TODO: implement` comment
- Correct imports stubbed out (even if functions are not yet implemented)

Specifically: `models.py`, `cli.py`, `summarizer.py`, `heuristics.py`, `generator.py`, `parsers/__init__.py`, `parsers/base.py`, `parsers/claude.py`

### 6. Create empty test files

For each test file in `tests/`, create it with:
- A module docstring
- One placeholder test: `def test_placeholder(): pass`

### 7. Initial commit and push

```
git add .
git commit -m "chore: initial project scaffold — handover v0.1.0"
git push origin main
```

### 8. Confirm setup complete

Tell me:
1. The GitHub repo URL (https://github.com/...)
2. The local path confirmed
3. The PyPI package name chosen (handover or handover-cli)
4. Any issues encountered

---

## What to do after Cowork finishes

Once Cowork confirms everything is set up:

1. Open Terminal
2. `cd /Users/mohankrishnaalavala/Documents/project_handover`
3. `claude`  ← Claude Code reads CLAUDE.md and is ready to implement from PLAN.md

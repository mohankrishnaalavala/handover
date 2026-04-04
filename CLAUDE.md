# handover — Universal AI Chat to Local Agent Handover Tool

## Project Goal
CLI tool that parses AI chat exports and generates CLAUDE.md + PLAN.md
artifacts for local terminal agents to ingest. Phase 1: Claude chat only.

## Tech Stack
- Language: Python 3.11+
- CLI: Click (with subcommands: main, list, init)
- Templates: Jinja2
- API: Anthropic SDK (claude-sonnet-4-6 for summarization)
- Testing: pytest + pytest-cov
- Packaging: pyproject.toml / hatchling

## Architecture Rules
- Parser uses adapter pattern: one class per source in parsers/
- BaseParser in parsers/base.py defines the interface all adapters must implement
- Summarizer calls Claude API unless --no-llm; then delegates to heuristics.py
- Heuristics are keyword-rule-based — keep them simple and documented
- Generator uses Jinja2 templates only — never hardcode output format in Python
- All data models are dataclasses in models.py with full type hints
- schema_version must be bumped in models.py when HandoverContext fields change

## Coding Standards
- Type hints on all functions and methods
- Docstrings on all public methods
- Tests required for: parser output, heuristics rules, generator file output
- Mocked API calls in test_summarizer.py — never hit real API in tests
- No dependencies beyond: click, anthropic, jinja2, pytest, pytest-cov

## Key Commands
- Run tests: pytest tests/ -v --cov=handover
- Install locally: pip install -e .
- Run CLI: handover --help

## Phase 1 Focus
- Claude adapter only (parsers/claude.py)
- Do NOT build ChatGPT adapter yet — that is Phase 2
- Both input formats: .jsonl (bulk) and .json (single chat via browser extension)

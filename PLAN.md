# Implementation Plan — handover v0.1.0
<!-- Generated from PRD Section 15 -->

## Setup
- [ ] Initialize repo, MIT license, pyproject.toml, .gitignore
- [ ] Create full folder structure per Section 12

## Models
- [ ] Implement ConversationMessage dataclass (models.py)
- [ ] Implement Decision and Task dataclasses (models.py)
- [ ] Implement HandoverContext dataclass with schema_version + source_version (models.py)

## Parser
- [ ] Implement BaseParser abstract class (parsers/base.py)
- [ ] Implement ClaudeParser for .jsonl bulk export (parsers/claude.py)
- [ ] Implement ClaudeParser for single-conversation .json (parsers/claude.py)
- [ ] Add format auto-detection (jsonl vs json vs markdown)
- [ ] Add source_version detection for Claude export format variants

## Summarizer
- [ ] Implement Summarizer using Anthropic API (summarizer.py)
- [ ] Write structured extraction prompt → returns valid HandoverContext JSON
- [ ] Add conflict resolution logic (latest decision wins by message order)
- [ ] Implement --no-llm delegation to heuristics.py

## Heuristics (--no-llm mode)
- [ ] Implement goal extraction rule (first user message / intent keywords)
- [ ] Implement decision extraction rule (keyword matching)
- [ ] Implement constraint extraction rule
- [ ] Implement non-goals extraction rule
- [ ] Implement task extraction rule (lists + "next steps" patterns)
- [ ] Implement tech stack extraction (bundled keyword list)
- [ ] Conflict resolution: last occurrence wins

## Generator
- [ ] Implement Generator with Jinja2 (generator.py)
- [ ] Write CLAUDE.md template (templates/claude_md.j2)
- [ ] Write PLAN.md template (templates/plan_md.j2)

## CLI
- [ ] Implement main command with all flags (cli.py)
- [ ] Implement `handover list` subcommand
- [ ] Implement `handover init` subcommand
- [ ] Implement --dry-run mode with formatted console output
- [ ] Implement --launch flag (exec `claude` in output dir after writing)

## Tests
- [ ] test_parser.py — single JSON + bulk JSONL fixtures
- [ ] test_heuristics.py — each rule tested independently
- [ ] test_summarizer.py — mocked API, validate HandoverContext schema
- [ ] test_generator.py — assert file output matches expected structure
- [ ] Add anonymized test fixtures to tests/fixtures/

## Docs + OSS
- [ ] README.md with --dry-run terminal demo block
- [ ] CONTRIBUTING.md with adapter contribution guide
- [ ] docs/adding-an-adapter.md (Phase 2 contributor guide)
- [ ] docs/output-format.md
- [ ] GitHub Actions CI (ci.yml)
- [ ] GitHub Actions Release (release.yml) — PyPI Trusted Publisher
- [ ] GitHub issue + PR templates
- [ ] Publish v0.1.0 to PyPI

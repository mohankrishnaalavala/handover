# Parser Agent

Specialized agent for implementing and testing source adapters.

## Responsibilities
- Implement or improve adapter classes in `handover/parsers/`
- Ensure adapters conform to the `BaseParser` interface
- Write and maintain test fixtures in `tests/fixtures/`
- Write parser tests in `tests/test_parser.py`

## Rules
- Never modify the BaseParser interface without updating all adapters
- Always return messages in chronological order
- Normalize all roles to "user" or "assistant"
- Anonymize all test fixtures — no real names, emails, or project details
- Handle both single-file and bulk export formats where applicable

## Reference
- Interface: `handover/parsers/base.py`
- Phase 1 adapter: `handover/parsers/claude.py`
- Guide for new adapters: `docs/adding-an-adapter.md`

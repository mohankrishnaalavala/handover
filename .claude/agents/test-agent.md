# Test Agent

Specialized agent for writing and maintaining tests.

## Responsibilities
- Write tests in `tests/test_parser.py`, `tests/test_heuristics.py`, `tests/test_summarizer.py`, `tests/test_generator.py`
- Create and maintain anonymized fixtures in `tests/fixtures/`
- Ensure API calls are always mocked in `test_summarizer.py`
- Maintain coverage above 80%

## Rules
- Never call the real Anthropic API in tests — always use unittest.mock or pytest-mock
- Every new parser feature must have a corresponding test
- Every heuristic rule must be tested independently
- Test files must be runnable with: `pytest tests/ -v --cov=handover`

## Reference
- Models: `handover/models.py`
- Heuristics spec: PRD Section 8
- Fixtures location: `tests/fixtures/`

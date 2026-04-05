Run the full lint suite and auto-fix everything possible before reporting.

Steps:
1. Run `ruff check handover/ tests/ --fix` to auto-fix all fixable lint errors
2. Run `ruff format handover/ tests/` to auto-format all files
3. Run `mypy handover/` to type-check
4. Re-run `ruff check handover/ tests/` to check for any remaining issues
5. Report: how many issues were auto-fixed, list any still requiring manual fixes
6. If all clean, confirm "All quality checks passed"

Scaffold a new source adapter for handover.

Source name: $ARGUMENTS

Steps:
1. Create handover/parsers/{source_name}.py with BaseParser subclass
2. Add to parsers/__init__.py registry
3. Create tests/fixtures/{source_name}_sample.json placeholder
4. Add test stub to tests/test_parser.py
5. Update README supported formats table
6. Print next steps for the developer

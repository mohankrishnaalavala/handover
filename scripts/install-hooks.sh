#!/usr/bin/env bash
# Install git hooks from scripts/ into .git/hooks/
# Run once after cloning: bash scripts/install-hooks.sh
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/scripts/pre-push" "$REPO_ROOT/.git/hooks/pre-push"
chmod +x "$REPO_ROOT/.git/hooks/pre-push"
echo "Installed pre-push hook. Lint will run before every git push."

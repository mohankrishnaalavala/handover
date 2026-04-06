"""
handover/targets/__init__.py

Target adapter registry.

Mirrors the source adapter registry in handover/parsers/__init__.py.
Each entry maps a --target name to its adapter class.

To add a new target:
  1. Create handover/targets/<name>.py subclassing BaseTarget
  2. Add an entry to TARGET_REGISTRY below

Phase 5 — Multi-Target Agents.
"""

from __future__ import annotations

from handover.targets.aider import AiderTarget
from handover.targets.base import BaseTarget
from handover.targets.claude_code import ClaudeCodeTarget
from handover.targets.codex import CodexTarget
from handover.targets.goose import GooseTarget

TARGET_REGISTRY: dict[str, type[BaseTarget]] = {
    "claude-code": ClaudeCodeTarget,
    "codex": CodexTarget,
    "aider": AiderTarget,
    "goose": GooseTarget,
}


def get_target(name: str) -> BaseTarget:
    """
    Instantiate a target adapter by name.

    Args:
        name: Target identifier (e.g. 'codex', 'aider', 'goose').
              Use 'claude-code' for the default Claude Code target.
              Note: ClaudeCodeTarget accepts an optional template_dir —
              construct it directly when you need custom templates.

    Raises:
        ValueError: If name is not in the registry.

    Returns:
        An instantiated BaseTarget subclass.
    """
    if name not in TARGET_REGISTRY:
        raise ValueError(
            f"No target registered for '{name}'. "
            f"Available targets: {sorted(TARGET_REGISTRY)}"
        )
    return TARGET_REGISTRY[name]()


def list_targets() -> list[str]:
    """Return all registered target names in registration order."""
    return list(TARGET_REGISTRY)


__all__ = [
    "BaseTarget",
    "ClaudeCodeTarget",
    "CodexTarget",
    "AiderTarget",
    "GooseTarget",
    "TARGET_REGISTRY",
    "get_target",
    "list_targets",
]

"""
handover/grouping.py

v1.2.0 — Heuristic project grouping from conversation titles.

Groups conversations by inferred project name using token overlap.
No NLP dependencies — pure stdlib string operations.
"""

from __future__ import annotations

import re
from collections import defaultdict

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "for",
        "with",
        "and",
        "or",
        "to",
        "in",
        "on",
        "of",
        "is",
        "it",
        "by",
        "at",
        "from",
        "as",
        "about",
        "how",
        "what",
        "my",
        "this",
        "that",
        "i",
        "me",
    }
)

_SEPARATORS = re.compile(r"\s*[-—:|/]\s*")


def group_by_project(
    conversations: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Group conversations by inferred project name from titles.

    Strategy:
    1. Split titles on common separators (-, --, :, |, /)
    2. If left-hand prefix is shared by 2+ conversations, that's the project
    3. Fall back to significant-token overlap for non-separator titles
    4. Ungrouped titles go to "(ungrouped)"

    Args:
        conversations: List of dicts with at least "title" key.

    Returns:
        Ordered dict mapping project name -> list of conversations.
    """
    if not conversations:
        return {}

    # Phase 1: try separator-based prefix grouping
    prefix_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    no_prefix: list[dict[str, str]] = []

    for conv in conversations:
        title = conv.get("title", "")
        prefix = _extract_prefix(title)
        if prefix:
            prefix_map[prefix].append(conv)
        else:
            no_prefix.append(conv)

    # Prefixes with 2+ conversations are projects; singletons go back to pool
    groups: dict[str, list[dict[str, str]]] = {}
    remaining: list[dict[str, str]] = list(no_prefix)
    for prefix, convs in prefix_map.items():
        if len(convs) >= 2:
            groups[prefix] = convs
        else:
            remaining.extend(convs)

    # Phase 2: token-overlap grouping for remaining
    if remaining:
        token_groups = _group_by_tokens(remaining)
        groups.update(token_groups)

    return groups


def filter_by_project(
    conversations: list[dict[str, str]],
    project_name: str,
) -> list[dict[str, str]]:
    """Return conversations whose inferred project matches project_name.

    Uses normalized token overlap: a conversation matches if all significant
    tokens in the project name appear in the conversation title.
    """
    target_tokens = _tokenize(project_name)
    if not target_tokens:
        return []

    result: list[dict[str, str]] = []
    for conv in conversations:
        title = conv.get("title", "")
        title_tokens = _tokenize(title)
        if target_tokens.issubset(title_tokens):
            result.append(conv)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_prefix(title: str) -> str:
    """Extract the left-hand prefix before a separator, if any."""
    parts = _SEPARATORS.split(title, maxsplit=1)
    if len(parts) >= 2:
        prefix = parts[0].strip()
        # Only use prefix if it's meaningful (2+ chars)
        if len(prefix) >= 2:
            return prefix
    return ""


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on whitespace/punctuation, remove stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) >= 2}


def _group_by_tokens(
    conversations: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Group conversations by significant token overlap."""
    if not conversations:
        return {}

    # Build token sets per conversation
    token_sets = [_tokenize(c.get("title", "")) for c in conversations]

    # Find groups by pairwise overlap (simple O(n^2) — fine for small n)
    assigned: set[int] = set()
    groups: dict[str, list[dict[str, str]]] = {}

    for i in range(len(conversations)):
        if i in assigned:
            continue
        cluster = [i]
        shared = set(token_sets[i])
        for j in range(i + 1, len(conversations)):
            if j in assigned:
                continue
            overlap = token_sets[i] & token_sets[j]
            if len(overlap) >= 2:
                cluster.append(j)
                shared &= token_sets[j]

        if len(cluster) >= 2 and shared:
            # Project name = the shared tokens joined
            project_name = " ".join(sorted(shared)).title()
            groups[project_name] = [conversations[idx] for idx in cluster]
            assigned.update(cluster)

    # Ungrouped
    ungrouped = [conversations[i] for i in range(len(conversations)) if i not in assigned]
    if ungrouped:
        groups["(ungrouped)"] = ungrouped

    return groups

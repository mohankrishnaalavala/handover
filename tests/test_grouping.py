"""
Tests for handover/grouping.py.

Validates project inference from conversation titles:
prefix grouping, token overlap, ungrouped bucket, and filtering.
"""

from __future__ import annotations

from handover.grouping import filter_by_project, group_by_project

# ---------------------------------------------------------------------------
# group_by_project
# ---------------------------------------------------------------------------


class TestGroupByProject:
    def test_shared_prefix_groups(self) -> None:
        convs = [
            {"id": "1", "title": "Portfolio Website - API Design", "date": "2026-03-01"},
            {"id": "2", "title": "Portfolio Website - Frontend", "date": "2026-03-05"},
            {"id": "3", "title": "Portfolio Website - Deploy", "date": "2026-03-10"},
        ]
        groups = group_by_project(convs)
        assert "Portfolio Website" in groups
        assert len(groups["Portfolio Website"]) == 3

    def test_different_prefixes(self) -> None:
        convs = [
            {"id": "1", "title": "Auth Service - Login", "date": "2026-03-01"},
            {"id": "2", "title": "Auth Service - Signup", "date": "2026-03-05"},
            {"id": "3", "title": "Portfolio Website - Home", "date": "2026-03-10"},
            {"id": "4", "title": "Portfolio Website - About", "date": "2026-03-15"},
        ]
        groups = group_by_project(convs)
        assert len(groups) == 2
        assert "Auth Service" in groups
        assert "Portfolio Website" in groups

    def test_ungrouped_bucket(self) -> None:
        convs = [
            {"id": "1", "title": "Something unique", "date": "2026-03-01"},
            {"id": "2", "title": "Another unique chat", "date": "2026-03-05"},
        ]
        groups = group_by_project(convs)
        # These don't share prefix or 2+ significant tokens
        assert "(ungrouped)" in groups

    def test_empty_input(self) -> None:
        assert group_by_project([]) == {}

    def test_single_conversation(self) -> None:
        convs = [{"id": "1", "title": "Solo chat", "date": "2026-03-01"}]
        groups = group_by_project(convs)
        # Single conversation can't form a group of 2+
        assert "(ungrouped)" in groups

    def test_token_overlap_grouping(self) -> None:
        convs = [
            {"id": "1", "title": "Build the auth system", "date": "2026-03-01"},
            {"id": "2", "title": "Auth system testing", "date": "2026-03-05"},
            {"id": "3", "title": "Totally unrelated topic", "date": "2026-03-10"},
        ]
        groups = group_by_project(convs)
        # "auth" and "system" are shared tokens
        found_auth_group = False
        for _name, members in groups.items():
            member_ids = {m["id"] for m in members}
            if {"1", "2"}.issubset(member_ids):
                found_auth_group = True
        assert found_auth_group


# ---------------------------------------------------------------------------
# filter_by_project
# ---------------------------------------------------------------------------


class TestFilterByProject:
    def test_fuzzy_match(self) -> None:
        convs = [
            {"id": "1", "title": "Portfolio Website - API Design", "date": "2026-03-01"},
            {"id": "2", "title": "Portfolio Website - Frontend", "date": "2026-03-05"},
            {"id": "3", "title": "Auth Service - Login", "date": "2026-03-10"},
        ]
        result = filter_by_project(convs, "Portfolio Website")
        assert len(result) == 2
        assert all("Portfolio" in c["title"] for c in result)

    def test_no_match(self) -> None:
        convs = [
            {"id": "1", "title": "Auth Service - Login", "date": "2026-03-01"},
        ]
        result = filter_by_project(convs, "Portfolio Website")
        assert result == []

    def test_empty_project_name(self) -> None:
        convs = [{"id": "1", "title": "Something", "date": "2026-03-01"}]
        assert filter_by_project(convs, "") == []

    def test_empty_conversations(self) -> None:
        assert filter_by_project([], "Portfolio") == []

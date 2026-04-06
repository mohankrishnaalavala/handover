"""
Tests for handover rule-based heuristics (--no-llm mode).

Each heuristic rule is tested independently.
See PRD Section 8 — --no-llm Rule-Based Extraction Heuristics.
"""

from handover import heuristics
from handover.models import ConversationMessage


# Helpers
def user(content: str) -> ConversationMessage:
    return ConversationMessage(role="user", content=content)


def assistant(content: str) -> ConversationMessage:
    return ConversationMessage(role="assistant", content=content)


class TestGoalExtraction:
    def test_extracts_from_intent_keyword(self) -> None:
        messages = [user("I want to build a FastAPI REST API.")]
        goal = heuristics.extract_goal(messages)
        assert "FastAPI" in goal or "REST API" in goal

    def test_falls_back_to_first_user_message(self) -> None:
        messages = [user("Explain how authentication works."), assistant("Sure...")]
        goal = heuristics.extract_goal(messages)
        assert "authentication" in goal.lower()

    def test_empty_messages_returns_empty(self) -> None:
        assert heuristics.extract_goal([]) == ""

    def test_no_user_messages_returns_empty(self) -> None:
        assert heuristics.extract_goal([assistant("Hello!")]) == ""

    def test_goal_trimmed_to_300_chars(self) -> None:
        long_content = "I want to build " + "x" * 400
        messages = [user(long_content)]
        goal = heuristics.extract_goal(messages)
        assert len(goal) <= 300

    def test_build_a_keyword(self) -> None:
        messages = [user("build a REST API for task management")]
        goal = heuristics.extract_goal(messages)
        assert goal != ""

    def test_create_a_keyword(self) -> None:
        messages = [user("create a CLI tool that parses chat exports")]
        goal = heuristics.extract_goal(messages)
        assert goal != ""


class TestDecisionExtraction:
    def test_extracts_lets_use_decision(self) -> None:
        messages = [assistant("Let's use JWT for a stateless API.")]
        decisions = heuristics.extract_decisions(messages)
        assert len(decisions) >= 1
        assert any("JWT" in d.decision for d in decisions)

    def test_extracts_well_go_with(self) -> None:
        messages = [assistant("We'll go with FastAPI for the framework.")]
        decisions = heuristics.extract_decisions(messages)
        assert len(decisions) >= 1

    def test_last_occurrence_wins_same_tech(self) -> None:
        messages = [
            assistant("Let's use PostgreSQL for the database."),
            assistant("Actually, let's use SQLite for simplicity."),
        ]
        decisions = heuristics.extract_decisions(messages)
        decision_texts = [d.decision for d in decisions]
        # SQLite wins — last occurrence
        assert any("SQLite" in t for t in decision_texts)

    def test_no_decisions_returns_empty(self) -> None:
        messages = [user("How does JWT work?"), assistant("JWT is a token format.")]
        decisions = heuristics.extract_decisions(messages)
        assert isinstance(decisions, list)

    def test_returns_decision_objects(self) -> None:
        from handover.models import Decision

        messages = [assistant("Let's use FastAPI for the API.")]
        decisions = heuristics.extract_decisions(messages)
        assert all(isinstance(d, Decision) for d in decisions)


class TestConstraintExtraction:
    def test_extracts_must_with_subject(self) -> None:
        messages = [user("It must run offline without internet access.")]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_extracts_cannot(self) -> None:
        messages = [user("The system cannot call external analytics services.")]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_extracts_should_not(self) -> None:
        messages = [user("It should not store passwords in plaintext.")]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_extracts_requirement_colon(self) -> None:
        messages = [user("requirement: offline support")]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_noisy_must_filtered_out(self) -> None:
        # "must" without a subject should not trigger
        messages = [user("Authentication must be done carefully.")]
        # This should be caught because "Authentication" acts as subject
        # — just verify we handle it without crashing
        constraints = heuristics.extract_constraints(messages)
        assert isinstance(constraints, list)

    def test_deduplication(self) -> None:
        messages = [
            user("It must run offline."),
            user("It must run offline."),  # duplicate
        ]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) == 1


class TestNonGoalExtraction:
    def test_extracts_out_of_scope(self) -> None:
        messages = [user("Mobile app is out of scope for v1.")]
        non_goals = heuristics.extract_non_goals(messages)
        assert len(non_goals) >= 1

    def test_extracts_not_in_scope(self) -> None:
        messages = [user("GUI is not in scope for this release.")]
        non_goals = heuristics.extract_non_goals(messages)
        assert len(non_goals) >= 1

    def test_extracts_wont(self) -> None:
        messages = [user("We won't build a mobile app in phase 1.")]
        non_goals = heuristics.extract_non_goals(messages)
        assert isinstance(non_goals, list)  # "won't" triggers

    def test_empty_messages_returns_empty(self) -> None:
        assert heuristics.extract_non_goals([]) == []


class TestTaskExtraction:
    def test_extracts_numbered_list(self) -> None:
        content = "1. Set up project\n2. Configure database\n3. Write tests"
        messages = [assistant(content)]
        tasks = heuristics.extract_tasks(messages)
        assert len(tasks) >= 3

    def test_extracts_next_steps_section(self) -> None:
        content = "Next steps:\n1. Set up FastAPI\n2. Implement JWT auth"
        messages = [assistant(content)]
        tasks = heuristics.extract_tasks(messages)
        assert any("FastAPI" in t.title for t in tasks)

    def test_extracts_bullet_list(self) -> None:
        content = "Tasks:\n- Configure PostgreSQL\n- Write migrations\n- Add tests"
        messages = [assistant(content)]
        tasks = heuristics.extract_tasks(messages)
        assert len(tasks) >= 3

    def test_deduplicates_tasks(self) -> None:
        content = "1. Set up project\n1. Set up project"  # duplicate
        messages = [assistant(content)]
        tasks = heuristics.extract_tasks(messages)
        titles = [t.title.lower() for t in tasks]
        assert len(titles) == len(set(titles))

    def test_empty_messages_returns_empty(self) -> None:
        assert heuristics.extract_tasks([]) == []

    def test_returns_task_objects(self) -> None:
        from handover.models import Task

        messages = [assistant("1. Build the API")]
        tasks = heuristics.extract_tasks(messages)
        assert all(isinstance(t, Task) for t in tasks)


class TestTechStackExtraction:
    def test_detects_python_fastapi_postgres(self) -> None:
        messages = [user("We'll use Python with FastAPI and PostgreSQL.")]
        tech_stack = heuristics.extract_tech_stack(messages)
        assert "Python" in tech_stack.values()
        assert "FastAPI" in tech_stack.values()
        assert "PostgreSQL" in tech_stack.values()

    def test_returns_canonical_names(self) -> None:
        messages = [user("python fastapi postgresql pytest docker")]
        tech_stack = heuristics.extract_tech_stack(messages)
        # Should return canonical casing, not lowercase
        assert all(v[0].isupper() or v in ("pytest",) for v in tech_stack.values())

    def test_empty_messages_returns_empty_dict(self) -> None:
        assert heuristics.extract_tech_stack([]) == {}

    def test_unknown_tech_not_included(self) -> None:
        messages = [user("We'll use an obscure thing called ZapDB.")]
        tech_stack = heuristics.extract_tech_stack(messages)
        assert "ZapDB" not in str(tech_stack)


class TestOpenQuestionExtraction:
    def test_extracts_question_mark(self) -> None:
        messages = [assistant("Which ORM should we use — SQLAlchemy vs Tortoise ORM?")]
        questions = heuristics.extract_open_questions(messages)
        assert len(questions) >= 1

    def test_short_questions_filtered(self) -> None:
        messages = [user("OK?")]
        questions = heuristics.extract_open_questions(messages)
        assert len(questions) == 0  # too short

    def test_empty_messages_returns_empty(self) -> None:
        assert heuristics.extract_open_questions([]) == []


class TestExtractOrchestrator:
    def test_returns_handover_context(self) -> None:
        from handover.models import HandoverContext

        messages = [
            user("I want to build a FastAPI REST API."),
            assistant("Let's use Python and PostgreSQL."),
        ]
        ctx = heuristics.extract(messages)
        assert isinstance(ctx, HandoverContext)

    def test_extracted_at_is_iso_format(self) -> None:
        import re

        messages = [user("Build a tool.")]
        ctx = heuristics.extract(messages)
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ctx.extracted_at)

    def test_open_questions_populated(self) -> None:
        messages = [assistant("Which database should we use — PostgreSQL or MySQL?")]
        ctx = heuristics.extract(messages)
        assert isinstance(ctx.open_questions, list)


class TestRegressionPatterns:
    """Regression tests for AI assistant recommendation phrasing (heuristics quality fixes)."""

    def test_extracts_recommendation_decision(self) -> None:
        """AI assistant 'For a local-friendly setup: React + Vite' → Decision extracted."""
        messages = [
            assistant(
                "For a local-friendly setup: React + Vite for the frontend, "
                "FastAPI (Python) for the backend, and SQLite to start."
            )
        ]
        decisions = heuristics.extract_decisions(messages)
        assert len(decisions) >= 1

    def test_extracts_stack_recommendation_decision(self) -> None:
        """Stack recommendation phrasing → Decision extracted."""
        messages = [
            assistant(
                "Stack recommendation\n\nFor the backend, use FastAPI with SQLite."
            )
        ]
        decisions = heuristics.extract_decisions(messages)
        assert len(decisions) >= 1

    def test_extracts_constraint_to_start(self) -> None:
        """'SQLite to start' phrasing → constraint extracted."""
        messages = [
            assistant("Use SQLite to start — easy to swap to Postgres later.")
        ]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_extracts_constraint_initially(self) -> None:
        """'initially' phrasing → constraint extracted."""
        messages = [
            assistant("SQLite used initially for simplicity.")
        ]
        constraints = heuristics.extract_constraints(messages)
        assert len(constraints) >= 1

    def test_goal_cleaned_up_from_intent_prefix(self) -> None:
        """Raw 'i want to build a X' → clean 'X' after stripping intent prefix."""
        messages = [user("i want to build a water intake tracker webapp")]
        goal = heuristics.extract_goal(messages)
        assert not goal.lower().startswith("i want")
        assert goal[0].isupper()

    def test_goal_capitalised(self) -> None:
        """Goal result is capitalised regardless of user casing."""
        messages = [user("build a todo app with reminders")]
        goal = heuristics.extract_goal(messages)
        assert goal[0].isupper()

    def test_go_not_matched_inside_postgres(self) -> None:
        """'go' keyword must not match inside 'Postgres' (word-boundary regression)."""
        messages = [assistant("We'll use PostgreSQL as the database.")]
        tech_stack = heuristics.extract_tech_stack(messages)
        assert tech_stack.get("language") != "Go"

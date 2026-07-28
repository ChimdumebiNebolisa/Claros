"""Tests for Claros tutoring system prompt (Gemini Live)."""

from agent import build_system_prompt


def test_build_system_prompt_includes_assignment():
    """System prompt includes the assignment text."""
    assignment = "Question 1: What is 2+2?\n\nQuestion 2: What is 3+3?"
    prompt = build_system_prompt(assignment)
    assert "Question 1: What is 2+2?" in prompt
    assert "Question 2: What is 3+3?" in prompt


def test_build_system_prompt_includes_writing_rules():
    """System prompt includes key writing rules for answer readiness."""
    prompt = build_system_prompt("Question 1: Foo")
    assert "Tell me your final answer first" in prompt
    assert "Let me write that for question" in prompt


def test_deprecated_write_token_parser_removed():
    """Stage 10: legacy [WRITE:N] parser must not remain production surface."""
    import agent

    assert not hasattr(agent, "WriteTokenParser")

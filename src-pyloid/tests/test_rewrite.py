"""Tests for rewrite presets."""

from services.rewrite import rewrite_text


def test_grammar_correct_capitalizes_and_punctuates():
    assert rewrite_text("hello world", "grammar_correct") == "Hello world."


def test_professional_expands_contractions():
    result = rewrite_text("I can't do it", "professional")
    assert "cannot" in result.lower()


def test_casual_spoken_lowercases():
    result = rewrite_text("Hello World.", "casual_spoken")
    assert result == "hello world"


def test_concise_keeps_first_sentence():
    result = rewrite_text("First part. Second part.", "concise")
    assert result == "First part."


def test_empty_returns_empty():
    assert rewrite_text("   ", "grammar_correct") == ""

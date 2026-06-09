"""Tests for filler word removal."""

from services.filler_words import remove_filler_words


def test_removes_english_hesitations():
    assert remove_filler_words("um I uh think") == "I think"


def test_keeps_content_without_fillers():
    text = "ship the release today"
    assert remove_filler_words(text) == text


def test_casual_mode_keeps_soft_fillers():
    result = remove_filler_words("um basically I think", keep_for_casual=True)
    assert result == "basically I think"

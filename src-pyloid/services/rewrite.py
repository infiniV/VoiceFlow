"""Rule-based text rewrite presets — parity with iOS OfflineRewriteService."""

from typing import Literal

RewritePreset = Literal[
    "grammar_correct",
    "professional",
    "casual_spoken",
    "concise",
]

REWRITE_PRESETS = [
    "grammar_correct",
    "professional",
    "casual_spoken",
    "concise",
]

_FORMAL_REPLACEMENTS: list[tuple[str, str]] = [
    ("can't", "cannot"),
    ("won't", "will not"),
    ("don't", "do not"),
    ("doesn't", "does not"),
    ("isn't", "is not"),
    ("aren't", "are not"),
    ("wasn't", "was not"),
    ("weren't", "were not"),
    ("shouldn't", "should not"),
    ("wouldn't", "would not"),
    ("couldn't", "could not"),
    ("haven't", "have not"),
    ("hasn't", "has not"),
    ("hadn't", "had not"),
    ("didn't", "did not"),
    ("gonna", "going to"),
    ("wanna", "want to"),
    ("gotta", "got to"),
    ("kinda", "kind of"),
    ("sorta", "sort of"),
    ("yeah", "yes"),
    ("nah", "no"),
    ("okay", "understood"),
    ("ok", "understood"),
]


def _normalize_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    result = stripped[0].upper() + stripped[1:]
    if not result.endswith((".", "!", "?")):
        result += "."
    return result


def _formalize_sentence(text: str) -> str:
    result = _normalize_sentence(text)
    for casual, formal in _FORMAL_REPLACEMENTS:
        # Case-insensitive single-word replacement
        parts = result.split()
        replaced: list[str] = []
        for word in parts:
            core = word.strip(".,!?;:")
            trailing = word[len(core) :] if core else word
            if core.lower() == casual:
                replacement = formal
                if core and core[0].isupper():
                    replacement = replacement.capitalize()
                replaced.append(replacement + trailing)
            else:
                replaced.append(word)
        result = " ".join(replaced)
    return result


def _casualize_sentence(text: str) -> str:
    result = text.strip().lower()
    if result.endswith("."):
        result = result[:-1]
    return result


def _condense_sentence(text: str) -> str:
    for sep in (".", "!", "?"):
        if sep in text:
            first = text.split(sep)[0].strip()
            if first:
                return _normalize_sentence(first)
    words = text.split()
    if len(words) > 50:
        return _normalize_sentence(" ".join(words[:50]))
    return _normalize_sentence(text)


def rewrite_text(text: str, preset: str) -> str:
    """Apply a rewrite preset to transcribed text."""
    trimmed = text.strip()
    if not trimmed:
        return ""

    if preset == "grammar_correct":
        return _normalize_sentence(trimmed)
    if preset == "professional":
        return _formalize_sentence(trimmed)
    if preset == "casual_spoken":
        return _casualize_sentence(trimmed)
    if preset == "concise":
        return _condense_sentence(trimmed)
    return trimmed

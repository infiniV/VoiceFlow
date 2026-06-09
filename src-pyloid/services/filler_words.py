"""Filler word removal — parity with iOS FillerWordFilter."""

import re

_ENGLISH_FILLERS = {
    "um", "uh", "umm", "uhh", "hmm", "hm", "er", "erm", "ah", "ahh",
    "like", "basically", "literally", "actually", "honestly", "right",
    "so", "well", "anyway", "anyways", "obviously", "clearly",
    "kinda", "sorta",
}

_HEAVY_ENGLISH = {"um", "uh", "umm", "uhh", "hmm", "hm", "er", "erm"}

_LANGUAGE_FILLERS: dict[str, set[str]] = {
    "en": _ENGLISH_FILLERS,
    "es": {"eh", "este", "pues", "bueno", "entonces", "o sea", "ehm", "emm", "tipo", "sabes", "verdad"},
    "zh": {"那个", "就是", "然后", "嗯", "这个", "对"},
    "ja": {"えーと", "あの", "まあ", "なんか", "ちょっと", "えー"},
    "fr": {"euh", "bah", "ben", "bon", "genre", "quoi", "voilà", "enfin", "en", "fait", "hein"},
    "de": {"äh", "ähm", "also", "halt", "quasi", "irgendwie", "eigentlich", "naja"},
    "pt": {"tipo", "né", "assim", "então", "bom", "olha", "enfim", "pois", "sabe"},
    "ko": {"음", "어", "그", "저", "뭐", "좀", "이제", "근데"},
    "ar": {"يعني", "هيك", "شو", "طيب", "بس", "اه"},
    "hi": {"मतलब", "अच्छा", "बस"},
    "it": {"cioè", "allora", "praticamente", "tipo", "insomma", "ecco", "boh"},
    "ru": {"ну", "вот", "типа", "значит", "короче", "блин"},
}

_HEAVY_BY_LANG: dict[str, set[str]] = {
    "en": _HEAVY_ENGLISH,
    "es": {"eh", "este", "ehm", "emm"},
    "zh": {"那个", "就是", "嗯"},
    "ja": {"えーと", "あの"},
    "fr": {"euh", "bah", "ben"},
    "de": {"äh", "ähm"},
    "pt": {"tipo", "né"},
    "ko": {"음", "어"},
    "ar": {"يعني", "اه"},
    "hi": {"मतलब", "बस"},
    "it": {"cioè", "tipo"},
    "ru": {"ну", "вот", "типа"},
}


def _resolve_language(language: str) -> str:
    if language == "auto":
        return "en"
    return language if language in _LANGUAGE_FILLERS else "en"


def remove_filler_words(text: str, language: str = "en", keep_for_casual: bool = False) -> str:
    lang = _resolve_language(language)
    fillers = _LANGUAGE_FILLERS.get(lang, _ENGLISH_FILLERS)
    to_remove = _HEAVY_BY_LANG.get(lang, _HEAVY_ENGLISH) if keep_for_casual else fillers

    words = text.split()
    kept: list[str] = []
    for word in words:
        cleaned = word.lower().strip(".,!?;:\"'()[]")
        if cleaned not in to_remove:
            kept.append(word)

    result = " ".join(kept)
    result = re.sub(r"  +", " ", result)
    result = result.replace(" ,", ",")
    result = re.sub(r" \.", ".", result)
    return result.strip()

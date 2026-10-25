"""Romanization of non-Latin lyric lines.

Strategy
  * Detect the song's language once (kana => Japanese, hangul => Korean,
    only Han => Chinese). Han characters alone are ambiguous between Chinese
    and Japanese, so the song-level hint decides.
  * Japanese -> pykakasi (Hepburn), Chinese -> pypinyin (tone marks),
    Korean -> korean-romanizer, everything else -> unidecode (approximate).
  * Libraries are imported lazily; if one is missing that script falls back
    to unidecode so the app still starts.
"""
from __future__ import annotations

import logging
import re
import unicodedata

from .models import LyricLine

log = logging.getLogger(__name__)

_KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
_HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

_kakasi = None


def needs_romanization(text: str) -> bool:
    """True if the text has any letter that is not Latin script."""
    return any(ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN") for ch in text)


def detect_song_language(texts: list[str]) -> str:
    blob = "\n".join(texts)
    if _KANA.search(blob):
        return "ja"
    if _HANGUL.search(blob):
        return "ko"
    if _HAN.search(blob):
        return "zh"
    return ""


def _unidecode(text: str) -> str:
    try:
        from unidecode import unidecode
        return unidecode(text)
    except ImportError:
        return ""


def _japanese(text: str) -> str:
    global _kakasi
    import pykakasi
    if _kakasi is None:
        _kakasi = pykakasi.kakasi()
    return " ".join(i["hepburn"] for i in _kakasi.convert(text) if i["hepburn"].strip())


def _chinese(text: str) -> str:
    from pypinyin import Style, lazy_pinyin
    return " ".join(lazy_pinyin(text, style=Style.TONE))


def _korean(text: str) -> str:
    from korean_romanizer.romanizer import Romanizer
    return Romanizer(text).romanize()


def romanize_line(text: str, song_lang: str = "") -> str:
    if not text or not needs_romanization(text):
        return ""
    try:
        if _KANA.search(text) or (song_lang == "ja" and _HAN.search(text)):
            out = _japanese(text)
        elif _HANGUL.search(text):
            out = _korean(text)
        elif _HAN.search(text):
            out = _chinese(text)
        else:
            out = _unidecode(text)
    except Exception as e:      # missing lib or odd input -> degrade gracefully
        log.debug("romanize fallback (%s)", e)
        out = _unidecode(text)
    out = re.sub(r"\s+", " ", out).strip()
    return "" if out.lower() == text.lower() else out


def romanize_lines(lines: list[LyricLine]) -> None:
    """In place: fills `.romaji` on every line that needs it."""
    lang = detect_song_language([l.text for l in lines])
    for l in lines:
        l.romaji = romanize_line(l.text, lang)

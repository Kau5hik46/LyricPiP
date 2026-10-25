"""Parsers for LRC (timestamped) and plain lyrics."""
from __future__ import annotations

import re

from ..models import LyricLine

_STAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_OFFSET = re.compile(r"^\[offset:\s*(-?\d+)\s*\]", re.I)
_WORD_TAG = re.compile(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>")   # enhanced-LRC word times


def parse_lrc(text: str) -> list[LyricLine]:
    """'[01:02.50] hello' -> LyricLine(62.5, 'hello'). Handles multiple stamps
    per line ('[00:10.0][00:50.0] chorus'), [offset:ms] and enhanced word tags.
    Metadata tags ([ar:...], [ti:...]) are skipped automatically because they
    don't match the numeric time pattern."""
    offset = 0.0
    lines: list[LyricLine] = []
    for raw in text.splitlines():
        raw = raw.strip()
        m = _OFFSET.match(raw)
        if m:
            offset = int(m.group(1)) / 1000.0
            continue
        stamps = _STAMP.findall(raw)
        if not stamps:
            continue
        content = _WORD_TAG.sub("", _STAMP.sub("", raw)).strip()
        for mm, ss, frac in stamps:
            t = int(mm) * 60 + int(ss) + (int(frac) / 10 ** len(frac) if frac else 0.0)
            lines.append(LyricLine(max(t - offset, 0.0), content))
    lines.sort(key=lambda l: l.time)

    # Collapse runs of empty lines (instrumental gaps) into one.
    out: list[LyricLine] = []
    for l in lines:
        if not l.text and out and not out[-1].text:
            continue
        out.append(l)
    return out


def parse_plain(text: str) -> list[LyricLine]:
    """Un-synced lyrics: time = -1 for every line."""
    return [LyricLine(-1.0, ln.strip()) for ln in text.replace("\r", "").split("\n")]

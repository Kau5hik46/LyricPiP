"""Fuzzy scoring to pick the right song among search results."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, TypeVar

from ..models import TrackInfo

T = TypeVar("T")


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return max(0.9, SequenceMatcher(None, a, b).ratio())
    return SequenceMatcher(None, a, b).ratio()


def score(track: TrackInfo, title: str, artist: str, duration: float | None) -> float:
    """0..~1.15. Title counts more than artist; duration is a strong tie-breaker."""
    s = 0.6 * _sim(track.title, title) + 0.4 * _sim(track.artist, artist)
    if track.duration and duration:
        diff = abs(track.duration - duration)
        s += 0.15 if diff <= 3 else (-0.3 if diff > 10 else 0.0)
    return s


def best_match(track: TrackInfo,
               candidates: Iterable[tuple[T, str, str, float | None]],
               threshold: float = 0.55) -> T | None:
    """candidates: (payload, title, artist, duration_seconds). Returns best payload."""
    best, best_s = None, threshold
    for payload, title, artist, dur in candidates:
        s = score(track, title, artist, dur)
        if s > best_s:
            best, best_s = payload, s
    return best

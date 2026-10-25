"""Cleaning of messy track metadata.

Browsers (YouTube etc.) report titles like
"Artist - Song (Official Video) [4K]" and channel names like "Artist - Topic".
Providers match on clean strings, so we generate a few query *variants*.
"""
from __future__ import annotations

import re

from .models import TrackInfo

# "(Official Video)", "[Lyrics]", "(Remastered 2011)" ... removed entirely.
_NOISE = re.compile(
    r"[\(\[\{][^\)\]\}]*?(official|video|audio|lyrics?|visuali[sz]er|m/?v|hd|hq|4k|"
    r"remaster(ed)?|live|explicit)[^\)\]\}]*?[\)\]\}]", re.I)
# "feat. X", "(ft. X)" removed: providers index the main artist only.
_FEAT = re.compile(r"\s*[\(\[]?\s*\b(feat\.?|ft\.?|featuring)\b[^\)\]]*[\)\]]?", re.I)
_TOPIC = re.compile(r"\s*-\s*topic$|vevo$", re.I)
_SPACES = re.compile(r"\s{2,}")


def clean_title(title: str) -> str:
    title = _NOISE.sub("", title)
    title = _FEAT.sub("", title)
    return _SPACES.sub(" ", title).strip(" -–—|")


def clean_artist(artist: str) -> str:
    return _SPACES.sub(" ", _TOPIC.sub("", artist)).strip()


def first_artist(artist: str) -> str:
    """'A, B & C' -> 'A' (many providers only index the primary artist)."""
    return re.split(r"\s*(?:,|&|;|/|\bx\b|\band\b)\s*", artist, maxsplit=1)[0].strip()


def query_variants(track: TrackInfo) -> list[TrackInfo]:
    """Ordered, de-duplicated list of (artist,title) guesses to try."""
    title, artist = clean_title(track.title), clean_artist(track.artist)
    base = dict(album=track.album, duration=track.duration, player=track.player)
    out = [TrackInfo(title, artist, **base)]

    # "Artist - Title" packed into the title (typical for YouTube uploads).
    if " - " in title:
        left, right = (p.strip() for p in title.split(" - ", 1))
        out.append(TrackInfo(right, left, **base))
    # Only the primary artist.
    if first_artist(artist) and first_artist(artist) != artist:
        out.append(TrackInfo(title, first_artist(artist), **base))

    seen, unique = set(), []
    for t in out:
        k = (t.artist.lower(), t.title.lower())
        if t.title and k not in seen:
            seen.add(k)
            unique.append(t)
    return unique

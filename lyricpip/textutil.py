"""Cleaning of messy track metadata (YouTube & friends).

Browsers report things like
    "Artist - Song (Official Animated Music Video) [4K]"      artist = "ArtistVEVO"
    "Song | Animated Music Video"                             artist = "Some Channel"
    "【MV】Song Official Music Video"

How we tell *suffix noise* from the *real title*
------------------------------------------------
A piece of text is "noise" only if it is made ENTIRELY of known noise words
(and contains at least one strong one). So:
    "Animated Music Video"  -> every word is noise            -> removed
    "Video Games"           -> "games" is not a noise word    -> kept
    "Home Video"            -> "home" is not a noise word     -> kept
Trailing noise glued to a title ("Song Official Music Video") is only stripped
when the noise run is unambiguous (a multi-word run or a qualifier such as
"official"); a lone "video"/"audio" at the end is left alone.
Ambiguous cases are covered by trying several query *variants*, ending with a
conservative one that keeps the title almost untouched.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import TrackInfo

# Words that never belong to a song title when they form the whole suffix.
STRONG = {
    "official",
    "video",
    "mv",
    "m/v",
    "pv",
    "lyric",
    "lyrics",
    "audio",
    "visualizer",
    "visualiser",
    "animated",
    "animation",
    "clip",
    "hd",
    "hq",
    "4k",
    "8k",
    "1080p",
    "720p",
    "uhd",
    "remaster",
    "remastered",
    "explicit",
}
MODIFIER = {"music", "anime", "full"}  # only noise next to a STRONG word
FILLER = {"the", "a", "an", "new", "of"}  # tolerated inside brackets/segments
# A lone one of these at the end of a title is too ambiguous ("Home Video").
BARE_AMBIGUOUS = {"video", "audio", "clip"}

_YEAR = re.compile(r"^(19|20)\d{2}$")
_TOKEN = re.compile(r"[^\W_]+(?:/[^\W_]+)?")  # words, incl. "m/v"
_BRACKET = re.compile(r"[\(\[\{（［【〔][^\)\]\}）］】〕]*[\)\]\}）］】〕]")
_OFFICIAL_HINT = re.compile(
    r"\bofficial\b.*\b(video|audio|mv|m/v|visuali[sz]er|lyrics?|clip)\b"
    r"|\blyrics?\s+video\b|\bmusic\s+video\b",
    re.I,
)
_FEAT = re.compile(r"\s*[\(\[]?\s*\b(feat\.?|ft\.?|featuring)\b[^\)\]]*[\)\]]?", re.I)
_SPLIT = re.compile(r"\s+[-–—―]\s+|\s*[|｜]\s*|\s+//\s+")  # title separators
_QUOTED = re.compile(r"[「『“\"]([^」』”\"]{2,})[」』”\"]")  # Artist "Song" / 「Song」
_TOPIC = re.compile(r"\s*-\s*topic$|vevo$", re.I)
_SPACES = re.compile(r"\s{2,}")


# ---------------------------------------------------------------- noise tests
def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def is_noise_text(text: str) -> bool:
    """True if `text` consists only of noise vocabulary (and has a strong word)."""
    toks = _tokens(text)
    if not toks:
        return False
    allowed = STRONG | MODIFIER | FILLER
    if not all(t in allowed or _YEAR.match(t) for t in toks):
        return False
    return any(t in STRONG for t in toks)


def _strip_noise_brackets(s: str) -> str:
    """Remove "(Official Video)", "【MV】", "[4K]" ... but keep "(Live at Wembley)"."""

    def repl(m: re.Match) -> str:
        inner = m.group(0)[1:-1]
        return (
            " "
            if (is_noise_text(inner) or _OFFICIAL_HINT.search(inner))
            else m.group(0)
        )

    return _BRACKET.sub(repl, s)


def _strip_trailing_noise(seg: str) -> str:
    """'Song Official Music Video' -> 'Song' (never removes the first word)."""
    toks = list(_TOKEN.finditer(seg))
    i = len(toks)
    while i > 1 and toks[i - 1].group().lower() in (STRONG | MODIFIER):
        i -= 1
    run = [m.group().lower() for m in toks[i:]]
    if not run or not any(t in STRONG for t in run):
        return seg
    if len(run) == 1 and run[0] in BARE_AMBIGUOUS:
        return seg  # "Home Video" stays intact
    return seg[: toks[i].start()].rstrip(" -–—:,")


# ---------------------------------------------------------------- public API
def clean_title(title: str) -> str:
    """Return the song title with video/platform suffixes removed."""
    s = _strip_noise_brackets(title)
    cleaned = []
    for seg in (x.strip() for x in _SPLIT.split(s)):
        if seg:
            cleaned.append(_strip_trailing_noise(_FEAT.sub("", seg).strip()))
    kept = [x for x in cleaned if x and not is_noise_text(x)]
    if not kept:  # never erase everything
        kept = [x for x in cleaned if x][:1] or [title.strip()]
    return " - ".join(_SPACES.sub(" ", x).strip(" -–—|:,") for x in kept)


def clean_artist(artist: str) -> str:
    return _SPACES.sub(" ", _TOPIC.sub("", artist)).strip()


def first_artist(artist: str) -> str:
    """'A, B & C' -> 'A' (many providers only index the primary artist)."""
    return re.split(r"\s*(?:,|&|;|/|\bx\b|\band\b)\s*", artist, maxsplit=1)[0].strip()


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def _looks_like(a: str, b: str) -> bool:
    """Strict-ish name equality, used to spot which title segment is the artist."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def query_variants(track: TrackInfo) -> list[TrackInfo]:
    """Ordered, de-duplicated (artist, title) guesses; best guess first."""
    title, artist = clean_title(track.title), clean_artist(track.artist)
    segs = [s for s in title.split(" - ") if s]
    cands: list[tuple[str, str]] = []  # (title, artist)

    if len(segs) >= 2:
        # Use the player's artist field to decide which segment is the artist.
        idx = next(
            (i for i, s in enumerate(segs) if artist and _looks_like(s, artist)), None
        )
        if idx is not None:
            cands.append(
                (" - ".join(s for i, s in enumerate(segs) if i != idx), artist)
            )
        else:  # unknown channel: guess both orders
            cands += [(segs[1], segs[0]), (title, artist), (segs[0], segs[1])]
    else:
        cands.append((title, artist))

    # Artist "Song" / Artist「Song」 -> use the quoted part.
    for q in _QUOTED.findall(track.title):
        q = clean_title(q)
        if q and not is_noise_text(q):
            cands.append((q, artist))

    # Same guesses with only the primary artist.
    cands += [
        (t, first_artist(a))
        for t, a in list(cands)
        if first_artist(a) and first_artist(a) != a
    ]

    # Conservative fallback: raw title, only obvious bracket noise removed.
    cands.append((_strip_noise_brackets(track.title).strip(), artist))

    base = dict(album=track.album, duration=track.duration, player=track.player)
    seen, out = set(), []
    for t, a in cands:
        key = (t.lower(), a.lower())
        if t and key not in seen:
            seen.add(key)
            out.append(TrackInfo(t, a, **base))
    return out

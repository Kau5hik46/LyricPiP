"""Plain data classes shared by every layer (media, lyrics, UI).

Deliberately dependency-free (stdlib only) so it can be imported anywhere
and unit-tested without installing Qt or network libraries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrackInfo:
    """Metadata of the track the OS reports as playing."""
    title: str
    artist: str
    album: str = ""
    duration: float | None = None   # seconds, None if the player doesn't report it
    player: str = ""                # e.g. "spotify", "firefox", "Spotify.exe"

    @property
    def key(self) -> str:
        """Identity used to detect track changes and as cache key.
        Duration is excluded on purpose: some players report it late."""
        return f"{self.artist.strip().lower()}|{self.title.strip().lower()}"


@dataclass
class PlaybackState:
    """A snapshot of the player, taken at `sampled_at` (monotonic clock).

    OS APIs only give us the position occasionally, so the UI asks
    `current_position()` which extrapolates between snapshots.
    """
    track: TrackInfo | None = None
    playing: bool = False
    position: float = 0.0                       # seconds at sampled_at
    sampled_at: float = field(default_factory=time.monotonic)

    def current_position(self) -> float:
        pos = self.position
        if self.playing:
            pos += time.monotonic() - self.sampled_at
        if self.track and self.track.duration:
            pos = min(pos, self.track.duration)
        return max(pos, 0.0)


@dataclass
class LyricLine:
    time: float          # start time in seconds; -1 for unsynced lines
    text: str
    romaji: str = ""     # filled by romanize.py when the text is non-Latin


@dataclass
class RawLyrics:
    """What a provider returns: untouched text, parsed later by the manager."""
    provider: str
    lrc: str | None = None     # timestamped text ("[00:12.34] ...")
    plain: str | None = None   # un-timed text


@dataclass
class LyricsResult:
    provider: str
    lines: list[LyricLine]
    synced: bool

"""macOS: read Spotify and Apple Music through `osascript` (JavaScript for Automation).

Why only these two? Since macOS 15.4 the system-wide "now playing" API
(MediaRemote) is limited to entitled Apple binaries, so browsers cannot be read.
Players that expose an AppleScript dictionary can still be asked directly.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

from ..models import PlaybackState, TrackInfo

log = logging.getLogger(__name__)

# Spotify reports `duration` in milliseconds, Music in seconds.
DURATION_DIVISOR = {"Spotify": 1000, "Music": 1}


def parse_players(raw: str, is_ignored: Callable[[str], bool]) -> PlaybackState:
    """Turn the script's JSON list of player snapshots into the one state to show."""
    try:
        snapshots = json.loads(raw)
    except ValueError:
        log.warning("osascript returned invalid JSON: %r", raw[:200])
        return PlaybackState()
    candidates = [s for s in snapshots if s.get("title") and not is_ignored(s["player"])]
    if not candidates:
        return PlaybackState()
    return _to_playback_state(_prefer_playing(candidates))


def _prefer_playing(candidates: list[dict]) -> dict:
    # Falls back to script order, so a paused Spotify beats a paused Music.
    return next((c for c in candidates if c["state"] == "playing"), candidates[0])


def _to_playback_state(snapshot: dict) -> PlaybackState:
    player = snapshot["player"]
    duration = snapshot.get("duration")
    track = TrackInfo(
        title=snapshot["title"],
        artist=snapshot.get("artist") or "",
        album=snapshot.get("album") or "",
        duration=duration / DURATION_DIVISOR[player] if duration else None,
        player=player,
    )
    position = float(snapshot.get("position") or 0.0)
    return PlaybackState(track, snapshot["state"] == "playing", position, time.monotonic())

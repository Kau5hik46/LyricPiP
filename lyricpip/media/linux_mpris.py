"""Linux: read MPRIS2 players (Spotify, VLC, Rhythmbox, Firefox, Chrome, mpv...)
through the `playerctl` command line tool (apt install playerctl).

Why shell out instead of speaking D-Bus directly? It keeps the MVP tiny and
dependency-free. A later version could use `dbus-next` for push notifications
instead of polling.
"""
from __future__ import annotations

import logging
import subprocess
import time

from ..models import PlaybackState, TrackInfo
from .base import MediaWatcher

log = logging.getLogger(__name__)

SEP = "|||"
# One line per player. position/length are microseconds.
FORMAT = SEP.join(["{{status}}", "{{artist}}", "{{title}}", "{{album}}",
                   "{{mpris:length}}", "{{position}}", "{{playerName}}"])


class LinuxMPRISWatcher(MediaWatcher):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._warned = False

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._publish(self._poll())
            except Exception:
                log.exception("MPRIS poll failed")
                self._publish(PlaybackState())
            self._stop_event.wait(self.interval)

    def _poll(self) -> PlaybackState:
        try:
            proc = subprocess.run(["playerctl", "-a", "metadata", "--format", FORMAT],
                                  capture_output=True, text=True, timeout=3)
        except FileNotFoundError:
            if not self._warned:
                log.error("`playerctl` not found. Install it: sudo apt install playerctl")
                self._warned = True
            return PlaybackState()

        candidates = []
        for line in proc.stdout.splitlines():
            parts = line.split(SEP)
            if len(parts) != 7 or not parts[2]:
                continue
            status, artist, title, album, length, pos, player = parts
            if self._ignored(player):
                continue
            candidates.append((status, artist, title, album, length, pos, player))
        if not candidates:
            return PlaybackState()

        # Prefer a player that is currently Playing.
        candidates.sort(key=lambda c: c[0] != "Playing")
        status, artist, title, album, length, pos, player = candidates[0]

        def micros(v: str) -> float | None:
            try:
                return int(v) / 1_000_000
            except ValueError:
                return None

        track = TrackInfo(title, artist, album, micros(length), player)
        return PlaybackState(track, status == "Playing", micros(pos) or 0.0, time.monotonic())

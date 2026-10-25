"""Common base for the OS-specific "what is playing?" watchers.

Design: a background thread polls the OS and stores the latest PlaybackState.
The UI thread only calls `get_state()` (cheap, lock-protected), so slow OS
calls can never freeze the window.
"""
from __future__ import annotations

import threading

from ..models import PlaybackState


class MediaWatcher(threading.Thread):
    def __init__(self, interval: float = 1.0, ignore_players: list[str] | None = None):
        super().__init__(daemon=True, name=type(self).__name__)
        self.interval = interval
        self.ignore_players = [p.lower() for p in (ignore_players or [])]
        self._state = PlaybackState()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    # ---- API used by the UI ------------------------------------------------
    def get_state(self) -> PlaybackState:
        with self._lock:
            return self._state

    def stop(self) -> None:
        self._stop_event.set()

    # ---- helpers for subclasses -------------------------------------------
    def _publish(self, state: PlaybackState) -> None:
        with self._lock:
            self._state = state

    def _ignored(self, player_name: str) -> bool:
        name = player_name.lower()
        return any(p in name for p in self.ignore_players)

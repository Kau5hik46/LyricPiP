"""Windows: read the *System Media Transport Controls* (SMTC).

SMTC is the same API that powers the volume-flyout media widget. Spotify,
Apple Music, VLC, foobar2000 (with plugin) and Chromium/Firefox tabs all
publish into it, so one integration covers nearly every player.

Requires the `winrt-*` pip packages (see requirements.txt).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time

from ..models import PlaybackState, TrackInfo
from .base import MediaWatcher

log = logging.getLogger(__name__)


class WindowsSMTCWatcher(MediaWatcher):
    def run(self) -> None:
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as Manager,
                GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
            )
        except ImportError:
            log.error("winrt packages missing. Run: pip install -r requirements.txt")
            return
        # WinRT calls are async, so this thread owns a private asyncio loop.
        asyncio.run(self._main(Manager, Status))

    async def _main(self, Manager, Status) -> None:
        manager = await Manager.request_async()
        while not self._stop_event.is_set():
            try:
                self._publish(await self._poll(manager, Status))
            except Exception:
                log.exception("SMTC poll failed")
                self._publish(PlaybackState())
            await asyncio.sleep(self.interval)

    async def _poll(self, manager, Status) -> PlaybackState:
        # Several apps may have a session (e.g. paused Spotify + playing browser).
        # Prefer a session that is actually playing, else the OS "current" one.
        sessions = [s for s in manager.get_sessions()
                    if not self._ignored(s.source_app_user_model_id or "")]
        playing = [s for s in sessions
                   if s.get_playback_info().playback_status == Status.PLAYING]
        session = playing[0] if playing else (sessions[0] if sessions else None)
        if session is None:
            return PlaybackState()

        props = await session.try_get_media_properties_async()
        if not props.title:
            return PlaybackState()

        timeline = session.get_timeline_properties()
        is_playing = session.get_playback_info().playback_status == Status.PLAYING

        # `position` is only valid at `last_updated_time`; add the time since then.
        position = timeline.position.total_seconds()
        if is_playing:
            updated = timeline.last_updated_time
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=dt.timezone.utc)
            elapsed = (dt.datetime.now(dt.timezone.utc) - updated).total_seconds()
            position += max(0.0, min(elapsed, 3600.0))

        duration = (timeline.end_time - timeline.start_time).total_seconds()
        track = TrackInfo(
            title=props.title,
            artist=props.artist or "",
            album=props.album_title or "",
            duration=duration if duration > 0 else None,
            player=session.source_app_user_model_id or "",
        )
        return PlaybackState(track, is_playing, position, time.monotonic())

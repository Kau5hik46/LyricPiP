"""lyrics.ovh - free, no key, PLAIN (un-synced) lyrics only. Fallback source."""
from __future__ import annotations

from urllib.parse import quote

from ...models import RawLyrics, TrackInfo
from .base import Provider


class OvhProvider(Provider):
    name = "ovh"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        r = self.get(f"https://api.lyrics.ovh/v1/{quote(track.artist, safe='')}/{quote(track.title, safe='')}")
        if not r.ok:
            return None
        text = (r.json().get("lyrics") or "").strip()
        return RawLyrics(self.name, plain=text) if text else None

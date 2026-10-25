"""LRCLIB (https://lrclib.net) - open, free, no key. Best source of synced lyrics."""
from __future__ import annotations

from ...lyrics.matching import best_match
from ...models import RawLyrics, TrackInfo
from .base import Provider

API = "https://lrclib.net/api"


class LrclibProvider(Provider):
    name = "lrclib"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.http.headers["Lrclib-Client"] = "LyricPiP v0.1"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        # 1) Exact lookup. LRCLIB's /get needs album + duration to be precise.
        if track.album and track.duration:
            r = self.get(f"{API}/get", params={
                "track_name": track.title, "artist_name": track.artist,
                "album_name": track.album, "duration": int(round(track.duration))})
            if r.ok:
                d = r.json()
                if d.get("syncedLyrics") or d.get("plainLyrics"):
                    return RawLyrics(self.name, d.get("syncedLyrics"), d.get("plainLyrics"))

        # 2) Fuzzy search, then choose by title/artist/duration similarity.
        r = self.get(f"{API}/search", params={
            "track_name": track.title, "artist_name": track.artist})
        if not r.ok:
            return None
        items = [i for i in r.json() if i.get("syncedLyrics") or i.get("plainLyrics")]
        # Prefer entries that have synced lyrics.
        pick = best_match(track, (
            (i, i.get("trackName", ""), i.get("artistName", ""), i.get("duration"))
            for i in items if i.get("syncedLyrics"))) or best_match(track, (
            (i, i.get("trackName", ""), i.get("artistName", ""), i.get("duration"))
            for i in items))
        return RawLyrics(self.name, pick.get("syncedLyrics"), pick.get("plainLyrics")) if pick else None

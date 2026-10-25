"""NetEase Cloud Music - unofficial public web endpoints, no key.
Excellent coverage for Chinese/Japanese/Korean songs. May be geo/rate limited."""
from __future__ import annotations

from ...lyrics.matching import best_match
from ...models import RawLyrics, TrackInfo
from .base import Provider


class NeteaseProvider(Provider):
    name = "netease"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.http.headers["Referer"] = "https://music.163.com/"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        r = self.http.post("https://music.163.com/api/search/get/web",
                           data={"s": f"{track.title} {track.artist}", "type": 1,
                                 "offset": 0, "limit": 8, "total": "true"},
                           timeout=self.cfg.request_timeout)
        songs = (r.json().get("result") or {}).get("songs") or []
        song_id = best_match(track, (
            (s["id"], s["name"], ", ".join(a["name"] for a in s.get("artists", [])),
             (s.get("duration") or 0) / 1000 or None) for s in songs))
        if not song_id:
            return None

        r = self.get("https://music.163.com/api/song/lyric",
                     params={"id": song_id, "lv": -1, "tv": -1})
        lrc = (r.json().get("lrc") or {}).get("lyric")
        return RawLyrics(self.name, lrc=lrc) if lrc else None

"""KuGou - unofficial endpoints, 3 steps: song search -> lyric candidates -> download."""
from __future__ import annotations

import base64

from ...lyrics.matching import best_match
from ...models import RawLyrics, TrackInfo
from .base import Provider


class KugouProvider(Provider):
    name = "kugou"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        # 1) find the song -> its file hash
        r = self.get("https://mobileservice.kugou.com/api/v3/search/song", params={
            "format": "json", "keyword": f"{track.artist} {track.title}",
            "page": 1, "pagesize": 8, "showtype": 1})
        infos = (r.json().get("data") or {}).get("info") or []
        hit = best_match(track, (
            (i, i.get("songname", ""), i.get("singername", ""), i.get("duration"))
            for i in infos))
        if not hit:
            return None

        # 2) list lyric candidates for that hash
        r = self.get("https://lyrics.kugou.com/search", params={
            "ver": 1, "man": "yes", "client": "pc",
            "keyword": f"{hit['singername']} - {hit['songname']}",
            "duration": int((hit.get("duration") or 0) * 1000), "hash": hit["hash"]})
        cands = r.json().get("candidates") or []
        if not cands:
            return None

        # 3) download the best candidate (content is base64 LRC)
        c = cands[0]
        r = self.get("https://lyrics.kugou.com/download", params={
            "ver": 1, "client": "pc", "id": c["id"], "accesskey": c["accesskey"],
            "fmt": "lrc", "charset": "utf8"})
        content = r.json().get("content")
        if not content:
            return None
        text = base64.b64decode(content).decode("utf-8", "replace").lstrip("\ufeff")
        return RawLyrics(self.name, lrc=text)

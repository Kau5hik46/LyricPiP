"""Genius - PLAIN lyrics only. Needs a free API token (https://genius.com/api-clients).
Set env GENIUS_TOKEN or "genius_token" in config.json. The official API returns
no lyric text, so we search via API then scrape the song page (fragile: if Genius
changes its HTML this provider silently stops working)."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...lyrics.matching import best_match
from ...models import RawLyrics, TrackInfo
from .base import Provider


class GeniusProvider(Provider):
    name = "genius"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        if not self.cfg.genius_token:
            return None                      # not configured -> skip quietly
        r = self.get("https://api.genius.com/search",
                     params={"q": f"{track.artist} {track.title}"},
                     headers={"Authorization": f"Bearer {self.cfg.genius_token}"})
        hits = [h["result"] for h in r.json()["response"]["hits"] if h["type"] == "song"]
        url = best_match(track, (
            (h["url"], h["title"], h["primary_artist"]["name"], None) for h in hits))
        if not url:
            return None

        html = self.get(url).text
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.select('div[data-lyrics-container="true"]')
        if not blocks:
            return None
        for b in blocks:
            for br in b.find_all("br"):
                br.replace_with("\n")
        text = "\n".join(b.get_text() for b in blocks)
        text = re.sub(r"\[.*?\]", "", text)          # drop [Chorus], [Verse 1] markers
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return RawLyrics(self.name, plain=text) if text else None

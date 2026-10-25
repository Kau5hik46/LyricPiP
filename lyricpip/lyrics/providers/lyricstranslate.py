"""LyricsTranslate (https://lyricstranslate.com) - STUB, disabled by default.

Why a stub?  The site has no public API, is protected by Cloudflare, publishes
user-submitted *translations* without timestamps, and its terms restrict
scraping. A reliable integration needs a headless browser or a licensed feed,
which is out of scope for an MVP.

To experiment: add "lyricstranslate" to `providers` in config.json and implement
`fetch` (search page -> song page -> parse the translation column), returning
RawLyrics(self.name, plain=text).
"""
from __future__ import annotations

import logging

from ...models import RawLyrics, TrackInfo
from .base import Provider

log = logging.getLogger(__name__)


class LyricsTranslateProvider(Provider):
    name = "lyricstranslate"

    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        log.info("lyricstranslate provider is a stub - see its docstring")
        return None

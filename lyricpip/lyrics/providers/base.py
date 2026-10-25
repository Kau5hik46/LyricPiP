"""Provider interface. To add a source: subclass Provider, implement `fetch`,
and register it in providers/__init__.py."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import requests

from ...config import Config
from ...models import RawLyrics, TrackInfo

log = logging.getLogger(__name__)
UA = "Mozilla/5.0 (X11; Linux x86_64) LyricPiP/0.1 (+https://github.com/your/LyricPiP)"


class Provider(ABC):
    name = "base"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        # One Session per provider: providers run in different threads.
        self.http = requests.Session()
        self.http.headers["User-Agent"] = UA

    def get(self, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", self.cfg.request_timeout)
        return self.http.get(url, **kw)

    @abstractmethod
    def fetch(self, track: TrackInfo) -> RawLyrics | None:
        """Return lyrics or None. May raise; `safe_fetch` handles that."""

    def safe_fetch(self, track: TrackInfo) -> RawLyrics | None:
        """A broken/slow site must never break the whole lookup."""
        try:
            res = self.fetch(track)
            log.info("%-9s %s", self.name, "hit" if res else "miss")
            return res
        except Exception as e:
            log.warning("%-9s failed: %s", self.name, e)
            return None

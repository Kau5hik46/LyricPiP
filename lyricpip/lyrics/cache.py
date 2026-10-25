"""Tiny on-disk cache so each song is only searched once.

Stored in:  Windows %LOCALAPPDATA%/LyricPiP/Cache/lyrics/   Linux ~/.cache/LyricPiP/lyrics/
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from platformdirs import user_cache_dir

from ..models import LyricLine, LyricsResult

log = logging.getLogger(__name__)


class LyricsCache:
    def __init__(self) -> None:
        self.dir = Path(user_cache_dir("LyricPiP", appauthor=False)) / "lyrics"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

    def load(self, key: str) -> LyricsResult | None:
        try:
            d = json.loads(self._path(key).read_text("utf-8"))
            return LyricsResult(d["provider"], [LyricLine(t, x) for t, x in d["lines"]], d["synced"])
        except FileNotFoundError:
            return None
        except Exception:
            log.warning("Corrupt cache entry for %s", key)
            return None

    def save(self, key: str, res: LyricsResult) -> None:
        try:
            self._path(key).write_text(json.dumps({
                "provider": res.provider, "synced": res.synced,
                "lines": [[l.time, l.text] for l in res.lines]}, ensure_ascii=False), "utf-8")
        except Exception:
            log.exception("Cache write failed")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

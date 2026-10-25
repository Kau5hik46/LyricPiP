"""Orchestrates: cache -> providers (in parallel) -> parsing -> romanization."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import Config
from ..models import LyricsResult, RawLyrics, TrackInfo
from ..romanize import romanize_lines
from ..textutil import query_variants
from .cache import LyricsCache
from .lrc import parse_lrc, parse_plain
from .providers import build_providers

log = logging.getLogger(__name__)


class LyricsManager:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cache = LyricsCache()
        self.providers = build_providers(cfg)

    def invalidate(self, track: TrackInfo) -> None:
        self.cache.delete(track.key)

    def get(self, track: TrackInfo) -> LyricsResult | None:
        """Blocking - call from a worker thread, never from the UI thread."""
        result = self.cache.load(track.key)
        if result is None:
            # Try the raw metadata first, then cleaned/split variants.
            for variant in query_variants(track):
                result = self._choose(self._query_all(variant))
                if result:
                    self.cache.save(track.key, result)   # cache BEFORE romanizing
                    break
        if result:
            romanize_lines(result.lines)
        return result

    # ------------------------------------------------------------------
    def _query_all(self, track: TrackInfo) -> list[RawLyrics]:
        """Ask every provider at once; return answers in priority order."""
        ex = ThreadPoolExecutor(max_workers=max(1, len(self.providers)))
        futures = {ex.submit(p.safe_fetch, track): i for i, p in enumerate(self.providers)}
        answers: list[tuple[int, RawLyrics]] = []
        try:
            for fut in as_completed(futures, timeout=20):
                raw = fut.result()
                if raw:
                    answers.append((futures[fut], raw))
        except Exception:
            log.warning("Some providers timed out")
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        return [raw for _, raw in sorted(answers, key=lambda a: a[0])]

    @staticmethod
    def _choose(raws: list[RawLyrics]) -> LyricsResult | None:
        # 1) best-priority provider with usable synced lyrics
        for r in raws:
            if r.lrc:
                lines = parse_lrc(r.lrc)
                if len(lines) >= 2:
                    return LyricsResult(r.provider, lines, True)
        # 2) otherwise plain text from the best-priority provider
        for r in raws:
            if r.plain and r.plain.strip():
                return LyricsResult(r.provider, parse_plain(r.plain), False)
        return None

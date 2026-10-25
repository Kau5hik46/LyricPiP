"""Provider registry. Order in config.json -> priority."""

from __future__ import annotations

import logging

from ...config import Config
from .base import Provider
from .genius import GeniusProvider
from .kugou import KugouProvider
from .lrclib import LrclibProvider
from .lyricstranslate import LyricsTranslateProvider
from .netease import NeteaseProvider
from .ovh import OvhProvider

REGISTRY: dict[str, type[Provider]] = {
    p.name: p
    for p in (
        LrclibProvider,
        NeteaseProvider,
        KugouProvider,
        OvhProvider,
        GeniusProvider,
        LyricsTranslateProvider,
    )
}

# Display + priority order used by the UI dropdown. Earlier = higher priority.
ALL_PROVIDERS = ["lrclib", "netease", "kugou", "ovh", "genius", "lyricstranslate"]


def build_providers(cfg: Config) -> list[Provider]:
    out = []
    for name in cfg.providers:
        cls = REGISTRY.get(name.lower())
        if cls:
            out.append(cls(cfg))
        else:
            logging.getLogger(__name__).warning("Unknown provider %r ignored", name)
    return out

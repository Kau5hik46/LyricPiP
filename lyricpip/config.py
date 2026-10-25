"""User settings persisted as JSON.

Location:
  Windows : %LOCALAPPDATA%/LyricPiP/config.json
  Linux   : ~/.config/LyricPiP/config.json
Unknown keys are ignored, so old/new versions can share a file.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir

load_dotenv()

log = logging.getLogger(__name__)
CONFIG_PATH = Path(user_config_dir("LyricPiP", appauthor=False)) / "config.json"


@dataclass
class Config:
    # Provider order = priority order. Synced lyrics from an earlier provider
    # win over later ones; un-synced (plain) text is only used as a fallback.
    # Available: lrclib, netease, kugou, ovh, genius, lyricstranslate (stub)
    providers: list[str] = field(
        default_factory=lambda: ["lrclib", "netease", "kugou", "ovh", "genius"]
    )
    genius_token: str = ""  # or set env var GENIUS_TOKEN
    request_timeout: float = 6.0  # seconds per HTTP request

    # Appearance / behaviour
    font_size: int = 22
    bg_alpha: int = 150  # 0-255 opacity of the dark background
    show_romanization: bool = True
    offset: float = 0.0  # seconds; + shows lyrics earlier, - later
    ignore_players: list[str] = field(
        default_factory=list
    )  # substrings, e.g. ["chrome"]

    # Window geometry (remembered between runs)
    x: int | None = None
    y: int | None = None
    width: int = 520
    height: int = 230

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            data = json.loads(CONFIG_PATH.read_text("utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        except FileNotFoundError:
            pass
        except Exception:
            log.exception("Could not read %s, using defaults", CONFIG_PATH)
        cfg.genius_token = cfg.genius_token or os.environ.get("GENIUS_TOKEN", "")
        return cfg

    def save(self) -> None:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), "utf-8")
        except Exception:
            log.exception("Could not save config")

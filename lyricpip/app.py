"""Application entry point: wires watcher + lyrics manager + overlay window."""
from __future__ import annotations

import logging
import os
import sys


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    # Wayland compositors (GNOME on Ubuntu 22.04+) ignore "always on top" for
    # native Wayland windows. Running through XWayland fixes that. Set
    # QT_QPA_PLATFORM=wayland yourself to opt out.
    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    # Imports after the env tweak so Qt picks it up.
    from PySide6.QtWidgets import QApplication

    from .config import Config
    from .lyrics.manager import LyricsManager
    from .media import create_watcher
    from .ui.overlay import Overlay

    cfg = Config.load()
    watcher = create_watcher(ignore_players=cfg.ignore_players)
    watcher.start()

    app = QApplication(sys.argv)
    app.setApplicationName("LyricPiP")
    win = Overlay(cfg, watcher, LyricsManager(cfg))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

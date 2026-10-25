"""The floating lyrics window (Qt / PySide6).

PiP behaviour
  * frameless + always-on-top + translucent dark background (alpha adjustable)
  * drag anywhere to move, drag any edge/corner to resize (the OS performs the
    drag via startSystemMove / startSystemResize, so it works on Windows, X11
    and Wayland and feels native)
  * right-click for settings; Ctrl+wheel = font size; [ ] = lyric timing

Threading: the UI thread never blocks. Lyric lookups run in a worker thread and
come back through the `lyrics_loaded` signal.
"""

from __future__ import annotations

import bisect
import html
import logging
import threading
from functools import reduce

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..lyrics.manager import LyricsManager
from ..lyrics.providers import ALL_PROVIDERS
from ..media.base import MediaWatcher
from ..models import LyricLine, LyricsResult, TrackInfo
from ..textutil import clean_artist, clean_title
from .search_dialog import ManualSearchDialog

log = logging.getLogger(__name__)

SOURCE_LABELS = {
    "lrclib": "LRCLIB (synced)",
    "netease": "NetEase (synced)",
    "kugou": "KuGou (synced)",
    "ovh": "lyrics.ovh (plain)",
    "genius": "Genius (plain, needs token)",
    "lyricstranslate": "LyricsTranslate (stub)",
}

EDGE = 8  # px of the border that acts as a resize handle
COL_CURRENT, COL_OTHER = "#FFFFFF", "#9AA4AF"
COL_ROMA_CURRENT, COL_ROMA_OTHER = "#7FD6FF", "#5F8FA8"


class Overlay(QWidget):
    lyrics_loaded = Signal(str, object)  # (track.key, LyricsResult | None)
    manual_loaded = Signal(
        str, str, object
    )  # (playing track.key, query label, result | None)

    def __init__(
        self, cfg: Config, watcher: MediaWatcher, manager: LyricsManager
    ) -> None:
        super().__init__()
        self.cfg, self.watcher, self.manager = cfg, watcher, manager

        # --- state --------------------------------------------------------
        self._track: TrackInfo | None = None
        self._lyrics: LyricsResult | None = None
        self._times: list[float] = []
        self._status = "Nothing playing"
        self._scroll = 0  # first-line index for unsynced lyrics
        self._last_render = None  # avoid re-rendering identical frames

        # --- window flags -------------------------------------------------
        self.setWindowTitle("LyricPiP")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(240, 90)
        self.resize(cfg.width, cfg.height)
        if cfg.x is not None and cfg.y is not None:
            self.move(cfg.x, cfg.y)

        # --- widgets ------------------------------------------------------
        self.header = QLabel()
        self.header.setStyleSheet("color:#7C8791; font-size:11px;")
        self.body = QLabel()
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.setWordWrap(True)
        for w in (self.header, self.body):
            # Labels must not swallow mouse events (we need them for drag/resize)
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # "Ignored" lets the window shrink below the text's natural width
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 10)
        lay.addWidget(self.header)
        lay.addWidget(self.body, 1)

        # --- wiring -------------------------------------------------------
        self.lyrics_loaded.connect(self._on_lyrics_loaded)
        self.manual_loaded.connect(self._on_manual_loaded)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)  # 10 Hz is plenty for line changes

    # ======================================================================
    # Main loop
    # ======================================================================
    def _tick(self) -> None:
        state = self.watcher.get_state()
        track = state.track

        if track is None:
            self._track, self._lyrics = None, None
            self._status = "Nothing playing"
            self._render(None)
            return

        if self._track is None or track.key != self._track.key:
            self._begin_track(track)

        if self._lyrics is None:
            self._render(None)
        elif self._lyrics.synced:
            pos = state.current_position() + self.cfg.offset
            self._render(max(bisect.bisect_right(self._times, pos) - 1, 0))
        else:
            self._render(self._scroll)

    # ----------------------------------------------------------------------
    def _begin_track(self, track: TrackInfo) -> None:
        self._track, self._lyrics, self._times, self._scroll = track, None, [], 0
        self._status = "Searching lyrics…"
        threading.Thread(target=self._fetch_worker, args=(track,), daemon=True).start()

    def _toggle_provider(self, name: str, on: bool) -> None:
        enabled = set(self.cfg.providers)
        enabled.add(name) if on else enabled.discard(name)
        # Keep the canonical priority order regardless of click order.
        self.cfg.providers = [p for p in ALL_PROVIDERS if p in enabled]
        self.cfg.save()  # persisted in config.json
        self.manager.reload_providers()  # new lookups use the new list
        self._refetch()  # drop the cached result and search again for the current song

    def _fetch_worker(self, track: TrackInfo) -> None:  # worker thread!
        try:
            res = self.manager.get(track)
        except Exception:
            log.exception("lyrics lookup crashed")
            res = None
        self.lyrics_loaded.emit(track.key, res)  # queued to UI thread

    def _on_lyrics_loaded(self, key: str, res: LyricsResult | None) -> None:
        if not self._track or key != self._track.key:
            return  # user already skipped on
        self._lyrics = res
        self._times = [l.time for l in res.lines] if res else []
        self._status = "" if res else "No lyrics found"
        self._last_render = None

    # ======================================================================
    # Rendering
    # ======================================================================
    def _line_html(self, line: LyricLine, current: bool) -> str:
        fs = self.cfg.font_size
        size = round(fs * 1.25) if current else fs
        color = COL_CURRENT if current else COL_OTHER
        weight = "bold" if current else "normal"
        text = html.escape(line.text) or "♪"
        out = (
            f'<div style="color:{color};font-size:{size}px;font-weight:{weight};'
            f'margin-top:4px;">{text}</div>'
        )
        if self.cfg.show_romanization and line.romaji:
            rc = COL_ROMA_CURRENT if current else COL_ROMA_OTHER
            out += (
                f'<div style="color:{rc};font-size:{round(fs * 0.8)}px;">'
                f"{html.escape(line.romaji)}</div>"
            )
        return out

    def _render(self, idx: int | None) -> None:
        sig = (
            idx,
            self._status,
            self.cfg.font_size,
            self.cfg.show_romanization,
            self.body.height(),
            id(self._lyrics),
            self._track.key if self._track else "",
        )
        if sig == self._last_render:
            return
        self._last_render = sig

        # Header: song + provider
        if self._track:
            src = f"  ·  {self._lyrics.provider}" if self._lyrics else ""
            sync = (
                ""
                if (self._lyrics is None or self._lyrics.synced)
                else "  ·  unsynced (scroll)"
            )
            self.header.setText(
                f"{self._track.title} — {self._track.artist}{src}{sync}"
            )
        else:
            self.header.setText("LyricPiP")

        if self._lyrics is None or idx is None:
            self.body.setText(
                f'<div style="color:{COL_OTHER};font-size:{self.cfg.font_size}px;">'
                f"{html.escape(self._status)}</div>"
            )
            return

        # How many lines fit? Estimate a slot height per line, keep current line high-ish.
        fs = self.cfg.font_size
        slot = fs * 1.5 + 6 + (fs * 1.1 if self.cfg.show_romanization else 0)
        n = max(1, int(self.body.height() / slot))
        before = (
            0
            if n == 1
            else (n // 2 if n <= 3 else n // 3)
            if self._lyrics.synced
            else 0
        )
        lines = self._lyrics.lines
        start = max(0, min(idx - before, len(lines) - 1))
        shown = lines[start : start + n]
        parts = [
            self._line_html(l, self._lyrics.synced and (start + i == idx))
            for i, l in enumerate(shown)
        ]
        self.body.setText("".join(parts))

    def paintEvent(self, _event) -> None:
        """Draw the rounded translucent background (text stays fully opaque)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(14, 16, 20, self.cfg.bg_alpha))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)

    # ======================================================================
    # Mouse: move + resize (delegated to the window system)
    # ======================================================================
    def _edges_at(self, pos) -> Qt.Edge:
        E = Qt.Edge
        edges = []
        if pos.x() <= EDGE:
            edges.append(E.LeftEdge)
        if pos.x() >= self.width() - EDGE:
            edges.append(E.RightEdge)
        if pos.y() <= EDGE:
            edges.append(E.TopEdge)
        if pos.y() >= self.height() - EDGE:
            edges.append(E.BottomEdge)
        return reduce(lambda a, b: a | b, edges, E(0))

    def mouseMoveEvent(self, ev) -> None:
        e, E = self._edges_at(ev.position().toPoint()), Qt.Edge
        has = lambda x: bool(e & x)  # noqa: E731
        if (has(E.LeftEdge) and has(E.TopEdge)) or (
            has(E.RightEdge) and has(E.BottomEdge)
        ):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (has(E.RightEdge) and has(E.TopEdge)) or (
            has(E.LeftEdge) and has(E.BottomEdge)
        ):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif has(E.LeftEdge) or has(E.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif has(E.TopEdge) or has(E.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, ev) -> None:
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        handle = self.windowHandle()
        edges = self._edges_at(ev.position().toPoint())
        if edges:
            handle.startSystemResize(edges)
        else:
            handle.startSystemMove()

    def mouseReleaseEvent(self, _ev) -> None:
        self._save_geometry()

    def wheelEvent(self, ev) -> None:
        step = 1 if ev.angleDelta().y() > 0 else -1
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._set_font(self.cfg.font_size + step * 2)
        elif self._lyrics and not self._lyrics.synced:
            self._scroll = max(
                0, min(self._scroll - step * 2, len(self._lyrics.lines) - 1)
            )

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key.Key_BracketRight:
            self._shift_offset(+0.5)
        elif ev.key() == Qt.Key.Key_BracketLeft:
            self._shift_offset(-0.5)
        elif (
            ev.key() == Qt.Key.Key_F
            and ev.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._manual_search()

    # ======================================================================
    # Context menu & settings
    # ======================================================================
    def contextMenuEvent(self, ev) -> None:
        m = QMenu(self)
        a = m.addAction("Show romanization")
        a.setCheckable(True)
        a.setChecked(self.cfg.show_romanization)
        a.triggered.connect(self._toggle_roma)

        m.addAction(
            "Font larger (Ctrl+wheel)", lambda: self._set_font(self.cfg.font_size + 2)
        )
        m.addAction("Font smaller", lambda: self._set_font(self.cfg.font_size - 2))

        bg = m.addMenu("Background opacity")
        for label, alpha in (
            ("Almost clear", 40),
            ("Light", 90),
            ("Medium", 150),
            ("Solid", 225),
        ):
            bg.addAction(label, lambda al=alpha: self._set_alpha(al))

        t = m.addMenu(f"Lyric timing ({self.cfg.offset:+.1f}s)")
        t.addAction("Show lyrics sooner  ]", lambda: self._shift_offset(+0.5))
        t.addAction("Show lyrics later   [", lambda: self._shift_offset(-0.5))
        t.addAction("Reset", lambda: self._shift_offset(None))

        src = m.addMenu("Lyric sources")
        for name in ALL_PROVIDERS:
            act = src.addAction(SOURCE_LABELS.get(name, name))
            act.setCheckable(True)
            act.setChecked(name in self.cfg.providers)
            act.triggered.connect(lambda on, n=name: self._toggle_provider(n, on))

        m.addAction("Re-fetch lyrics", self._refetch)
        m.addSeparator()
        m.addAction("Quit", self.close)
        m.exec(ev.globalPos())

    def _toggle_roma(self, on: bool) -> None:
        self.cfg.show_romanization = on
        self.cfg.save()

    def _set_font(self, size: int) -> None:
        self.cfg.font_size = max(10, min(size, 64))
        self.cfg.save()

    def _set_alpha(self, alpha: int) -> None:
        self.cfg.bg_alpha = alpha
        self.cfg.save()
        self.update()

    def _shift_offset(self, delta: float | None) -> None:
        self.cfg.offset = 0.0 if delta is None else round(self.cfg.offset + delta, 2)
        self.cfg.save()

    # ----------------------------------------------------------------------
    # Manual search: the QUERY comes from the user, the TIMING still comes from
    # the player (self.watcher), so lyrics stay in sync with what is playing.
    # ----------------------------------------------------------------------
    def _manual_search(self) -> None:
        playing = self._track
        if playing is None:
            QMessageBox.information(
                self,
                "LyricPiP",
                "Start playing a song first, so the lyrics can be synced to it.",
            )
            return
        dlg = ManualSearchDialog(
            self, clean_title(playing.title), clean_artist(playing.artist)
        )
        if dlg.exec() != ManualSearchDialog.DialogCode.Accepted:
            return
        title, artist = dlg.values()
        # Reuse the playing song's duration: it improves matching (picks the right
        # version) without the user having to type it.
        query = TrackInfo(
            title, artist, duration=playing.duration, player=playing.player
        )
        threading.Thread(
            target=self._manual_worker, args=(playing, query), daemon=True
        ).start()

    def _manual_worker(
        self, playing: TrackInfo, query: TrackInfo
    ) -> None:  # worker thread!
        try:
            res = self.manager.get(query, cache_key=playing.key, use_cache=False)
        except Exception:
            log.exception("manual lyrics lookup crashed")
            res = None
        label = f"{query.title} — {query.artist}" if query.artist else query.title
        self.manual_loaded.emit(playing.key, label, res)

    def _on_manual_loaded(self, key: str, label: str, res: LyricsResult | None) -> None:
        if res is None:
            QMessageBox.information(
                self,
                "LyricPiP",
                f"No lyrics found for “{label}”.\nThe current lyrics were kept.",
            )
            return
        if self._track and key == self._track.key:  # ignore if the song already changed
            self._lyrics = res
            self._times = [l.time for l in res.lines]
            self._status, self._scroll, self._last_render = "", 0, None

    def _refetch(self) -> None:
        if self._track:
            self.manager.invalidate(self._track)
            self._begin_track(self._track)

    def _save_geometry(self) -> None:
        g = self.geometry()
        self.cfg.x, self.cfg.y, self.cfg.width, self.cfg.height = (
            g.x(),
            g.y(),
            g.width(),
            g.height(),
        )
        self.cfg.save()

    def closeEvent(self, ev) -> None:
        self._save_geometry()
        self.watcher.stop()
        super().closeEvent(ev)

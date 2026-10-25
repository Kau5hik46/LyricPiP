"""Small modal dialog used for manual lyric search."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class ManualSearchDialog(QDialog):
    """Asks for title (required) and artist (optional).

    Pre-filled with the cleaned metadata of the playing song so the user only has
    to correct what is wrong. The overlay window is always-on-top, so this dialog
    asks for the same, otherwise it could open hidden behind the overlay.
    """

    def __init__(
        self, parent: QWidget | None, title: str = "", artist: str = ""
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search lyrics")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(400)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Song title (required)")
        self.artist_edit = QLineEdit(artist)
        self.artist_edit.setPlaceholderText("Artist (optional, improves accuracy)")

        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Artist", self.artist_edit)

        hint = QLabel(
            "Lyrics stay synced to the song that is currently playing, and the "
            "result is remembered for it. Use “Re-fetch lyrics” to go back to "
            "automatic matching."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Search")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def _on_accept(self) -> None:
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()  # title is mandatory
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.title_edit.text().strip(), self.artist_edit.text().strip()

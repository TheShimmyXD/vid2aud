"""Zona para soltar un archivo o hacer clic y buscarlo.

Vacia muestra la invitacion; con un archivo, su nombre y un resumen. Acepta
el arrastre de un solo archivo local y se resalta mientras pasa por encima.
No lee el archivo: solo entrega la ruta con ``file_dropped`` o pide el
selector con ``browse_requested``.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.blocks.icons import GlyphLabel
from ui.theme import SPACING_SCALE, Kind, Tone, set_drag_active, set_kind, set_tone

ICON_SIZE = 40
MIN_HEIGHT = 96


def local_file_from(mime: QMimeData) -> str:
    """La ruta del unico archivo local arrastrado, o cadena vacia."""
    urls = [url for url in mime.urls() if url.isLocalFile()]
    return urls[0].toLocalFile() if len(urls) == 1 else ""


class DropZone(QFrame):
    """
    Signals
    -------
    file_dropped(str)  -> ruta del archivo soltado.
    browse_requested() -> clic sobre la zona.
    """

    file_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_kind(self, Kind.DROP)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(MIN_HEIGHT)
        self._empty = (title, hint)

        row = QHBoxLayout(self)
        row.setContentsMargins(
            SPACING_SCALE[4], SPACING_SCALE[2], SPACING_SCALE[4], SPACING_SCALE[2]
        )
        row.setSpacing(SPACING_SCALE[3])
        self.icon = GlyphLabel("film-strip", ICON_SIZE, Tone.INFO)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel()
        set_kind(self.title_label, Kind.TITLE)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.hint_label = QLabel()
        set_tone(self.hint_label, Tone.MUTED)
        self.hint_label.setWordWrap(True)
        texts.addStretch(1)
        texts.addWidget(self.title_label)
        texts.addWidget(self.hint_label)
        texts.addStretch(1)
        row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(texts, 1)
        self.show_empty()

    def show_empty(self) -> None:
        self.icon.set_glyph("film-strip", Tone.INFO)
        self.title_label.setText(self._empty[0])
        self.hint_label.setText(self._empty[1])

    def show_file(self, name: str, info: str, glyph: str = "file-video", tone=Tone.INFO) -> None:
        self.icon.set_glyph(glyph, tone)
        metrics = self.title_label.fontMetrics()
        width = max(self.title_label.width(), 200)
        self.title_label.setText(metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, width))
        self.title_label.setToolTip(name)
        self.hint_label.setText(info)

    # -- Arrastrar y soltar ------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        if local_file_from(event.mimeData()):
            event.acceptProposedAction()
            set_drag_active(self, True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        set_drag_active(self, False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        set_drag_active(self, False)
        path = local_file_from(event.mimeData())
        if path:
            event.acceptProposedAction()
            self.file_dropped.emit(path)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.browse_requested.emit()
        super().mouseReleaseEvent(event)

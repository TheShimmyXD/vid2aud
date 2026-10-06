from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.mod_02_convert._02_coordinator import ConvertCoordinator
from modules.mod_02_convert.logic._02_logic_convert import ConvertState
from ui.blocks.drop_zone import DropZone, local_file_from
from ui.blocks.icons import GlyphButton, GlyphLabel
from ui.blocks.segmented import Segment, SegmentedButtons
from ui.blocks.status_line import StatusLine
from ui.theme import (
    WIDE,
    ButtonRole,
    Tone,
    mono_font,
    set_drag_active,
    set_role,
    set_tone,
)

DROP_TITLE = "Arrastra un video aquí"
DROP_HINT = "o haz clic para buscarlo"
VIDEO_FILTER = (
    "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.wmv *.flv *.mpg *.mpeg *.ts *.3gp);;"
    "Todos los archivos (*)"
)
CONVERT_TEXT = "Convertir"
CANCEL_TEXT = "Cancelar"


class ConvertWidget(QWidget):
    """
    Pantalla de conversion: elegir el video (soltar, buscar o escribir la ruta),
    elegir la salida, el formato y la calidad, y convertir.

    Solo habla con ``ConvertCoordinator``; no lee archivos ni conoce ffmpeg.
    """

    def __init__(self, coordinator: ConvertCoordinator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._coordinator = coordinator
        self._state = ConvertState.EMPTY
        self._last_output = ""
        self._requested_input = ""  # ultima ruta pedida al coordinador
        self._input_name = ""
        self.setAcceptDrops(True)
        self._build_ui()
        self._connect()
        self._apply_state(ConvertState.EMPTY)

    # -- Construccion ------------------------------------------

    def _build_ui(self) -> None:
        column = QVBoxLayout(self)
        column.setContentsMargins(WIDE.margin, WIDE.margin, WIDE.margin, WIDE.margin)
        column.setSpacing(WIDE.spacing + 2)

        self.drop_zone = DropZone(DROP_TITLE, DROP_HINT)
        column.addWidget(self.drop_zone)

        form = QGridLayout()
        form.setHorizontalSpacing(WIDE.spacing)
        form.setVerticalSpacing(WIDE.spacing)
        form.setColumnStretch(1, 1)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Ruta del video")
        self.input_edit.setAcceptDrops(False)
        self.input_button = GlyphButton("folder-open", "Buscar el video")
        self._add_row(form, 0, "Video", self.input_edit, self.input_button)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Dónde guardar el audio")
        self.output_edit.setAcceptDrops(False)
        self.output_button = GlyphButton("folder", "Elegir dónde guardar el audio")
        self._add_row(form, 1, "Audio", self.output_edit, self.output_button)

        formats = [Segment(k, label, tip) for k, label, tip in self._coordinator.formats()]
        self.format_buttons = SegmentedButtons(formats)
        self.format_buttons.select(self._coordinator.format_key)
        self._add_row(form, 2, "Formato", self.format_buttons)

        qualities = [Segment(k, label, tip) for k, label, tip in self._coordinator.qualities()]
        self.quality_buttons = SegmentedButtons(qualities)
        self.quality_buttons.select(self._coordinator.quality_key)
        self._add_row(form, 3, "Calidad", self.quality_buttons)

        estimate_row = QHBoxLayout()
        estimate_row.setSpacing(6)
        self.estimate_icon = GlyphLabel("file-audio", 16, Tone.INFO)
        self.estimate_label = QLabel()
        self.estimate_label.setFont(mono_font())
        set_tone(self.estimate_label, Tone.INFO)
        self.detail_label = QLabel()
        set_tone(self.detail_label, Tone.MUTED)
        estimate_row.addWidget(self.estimate_icon)
        estimate_row.addWidget(self.estimate_label)
        estimate_row.addWidget(self.detail_label, 1)
        form.addLayout(estimate_row, 4, 1, 1, 2)
        column.addLayout(form)
        column.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(WIDE.spacing)
        progress_box = QVBoxLayout()
        progress_box.setSpacing(4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel()
        self.progress_label.setFont(mono_font())
        set_tone(self.progress_label, Tone.MUTED)
        self.status_line = StatusLine()
        progress_box.addWidget(self.status_line)
        progress_box.addWidget(self.progress_label)
        progress_box.addWidget(self.progress_bar)
        self.open_button = QPushButton("Abrir carpeta")
        set_role(self.open_button, ButtonRole.QUIET)
        self.open_button.setToolTip("Abre la carpeta del audio")
        self.convert_button = QPushButton(CONVERT_TEXT)
        self.convert_button.setDefault(True)
        set_role(self.convert_button, ButtonRole.PRIMARY)
        footer.addLayout(progress_box, 1)
        footer.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignBottom)
        footer.addWidget(self.convert_button, 0, Qt.AlignmentFlag.AlignBottom)
        column.addLayout(footer)

    @staticmethod
    def _add_row(form: QGridLayout, row: int, label: str, field: QWidget, extra=None) -> None:
        caption = QLabel(label)
        set_tone(caption, Tone.MUTED)
        form.addWidget(caption, row, 0)
        if extra is None:
            form.addWidget(field, row, 1, 1, 2)
            return
        form.addWidget(field, row, 1)
        form.addWidget(extra, row, 2)

    def _connect(self) -> None:
        c = self._coordinator
        self.drop_zone.file_dropped.connect(self._select_input)
        self.drop_zone.browse_requested.connect(self._browse_input)
        self.input_button.clicked.connect(self._browse_input)
        self.input_edit.editingFinished.connect(self._on_input_typed)
        self.output_button.clicked.connect(self._browse_output)
        self.output_edit.editingFinished.connect(lambda: c.set_output_path(self.output_edit.text()))
        self.format_buttons.changed.connect(c.set_format)
        self.quality_buttons.changed.connect(c.set_quality)
        self.convert_button.clicked.connect(self._on_convert_clicked)
        self.open_button.clicked.connect(self._open_folder)

        c.state_changed.connect(self._on_state)
        c.source_changed.connect(self._on_source)
        c.plan_changed.connect(self._on_plan)
        c.output_changed.connect(self.output_edit.setText)
        c.progress.connect(self._on_progress)
        c.converted.connect(self._on_converted)

    # -- Acciones del usuario ----------------------------------

    def _browse_input(self) -> None:
        if self._state is ConvertState.CONVERTING:
            return
        start = self.input_edit.text() or self._coordinator.last_input_dir
        path, _ = QFileDialog.getOpenFileName(self, "Elegir video", start, VIDEO_FILTER)
        if path:
            self._select_input(path)

    def _on_input_typed(self) -> None:
        path = self.input_edit.text().strip()
        if path and path != self._requested_input:
            self._select_input(path)

    def _select_input(self, path: str) -> None:
        self._requested_input = path
        self.input_edit.setText(path)
        self._coordinator.select_input(path)

    def _browse_output(self) -> None:
        start = self.output_edit.text()
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar audio como", start, self._coordinator.output_filter()
        )
        if path:
            self._coordinator.set_output_path(path)

    def _on_convert_clicked(self) -> None:
        if self._state is ConvertState.CONVERTING:
            self._coordinator.cancel()
            self.convert_button.setEnabled(False)
            return
        self._coordinator.set_output_path(self.output_edit.text())
        if self._coordinator.output_exists():
            name = Path(self._coordinator.output_path).name
            answer = QMessageBox.question(
                self,
                "El audio ya existe",
                f"Ya existe «{name}». ¿Reemplazarlo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._coordinator.start_convert()

    def _open_folder(self) -> None:
        if self._last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._last_output).parent)))

    # -- Respuestas del coordinador ----------------------------

    def _on_state(self, payload: dict) -> None:
        self._apply_state(ConvertState(payload["state"]))
        message = payload.get("message", "")
        if self._state is ConvertState.INVALID:
            # El motivo ya sale en la zona del video; no se repite al pie.
            self.status_line.set_status("")
            self.drop_zone.show_file(self._input_name, message, "x-circle", Tone.ERROR)
        elif self._state is ConvertState.ERROR:
            self.status_line.set_status(message, Tone.ERROR)
        elif self._state is ConvertState.READY and message:
            self.status_line.set_status(message, Tone.WARNING)
        elif self._state in (ConvertState.PROBING, ConvertState.READY, ConvertState.CONVERTING):
            self.status_line.set_status("")

    def _on_source(self, payload: dict) -> None:
        self._input_name, info = payload["name"], payload["info"]
        self.drop_zone.show_file(self._input_name, info)
        if not info:
            self.estimate_label.clear()
            self.detail_label.clear()

    def _on_plan(self, payload: dict) -> None:
        self.estimate_label.setText(payload["estimate"])
        self.detail_label.setText(payload["detail"])
        tip = "Mismo audio del video, sin perder nada." if payload["copy"] else ""
        self.detail_label.setToolTip(tip)

    def _on_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"Convirtiendo… {percent} %")

    def _on_converted(self, payload: dict) -> None:
        if payload["ok"]:
            self._last_output = payload["output_path"]
            self.status_line.set_status(f"Listo · {payload['summary']}", Tone.OK)
            self.status_line.setToolTip(self._last_output)
            self.open_button.setVisible(True)
        elif payload["cancelled"]:
            self.status_line.set_status(payload["message"], Tone.WARNING)

    def _apply_state(self, state: ConvertState) -> None:
        self._state = state
        converting = state is ConvertState.CONVERTING
        has_plan = state in (ConvertState.READY, ConvertState.DONE, ConvertState.ERROR)
        for widget in (self.drop_zone, self.input_edit, self.input_button, self.output_edit,
                       self.output_button, self.format_buttons, self.quality_buttons):  # fmt: skip
            widget.setEnabled(not converting)
        self.convert_button.setEnabled(has_plan or converting)
        self.convert_button.setText(CANCEL_TEXT if converting else CONVERT_TEXT)
        set_role(self.convert_button, ButtonRole.DANGER if converting else ButtonRole.PRIMARY)
        self.progress_bar.setVisible(converting)
        self.progress_label.setVisible(converting)
        self.estimate_icon.setVisible(has_plan or converting)
        self.estimate_label.setVisible(has_plan or converting)
        self.detail_label.setVisible(has_plan or converting)
        if converting or state is ConvertState.PROBING:
            self.open_button.setVisible(False)
        if state is ConvertState.EMPTY:
            self.drop_zone.show_empty()
            self.open_button.setVisible(False)

    # -- Arrastrar sobre toda la pantalla ----------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        if self._state is not ConvertState.CONVERTING and local_file_from(event.mimeData()):
            event.acceptProposedAction()
            set_drag_active(self.drop_zone, True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        set_drag_active(self.drop_zone, False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (nombre impuesto por Qt)
        set_drag_active(self.drop_zone, False)
        path = local_file_from(event.mimeData())
        if path:
            event.acceptProposedAction()
            self._select_input(path)

    def closeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        self._coordinator.close()
        super().closeEvent(event)

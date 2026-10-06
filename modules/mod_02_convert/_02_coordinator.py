from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from config import AppConfig, save_app_config
from core.worker_runner import RequestSequence, start_worker, stop_thread
from modules.mod_02_convert.logic._02_logic_convert import ConvertLogic
from modules.mod_02_convert.logic._02_logic_presets import (
    FORMATS,
    QUALITIES,
    EncodePlan,
    SourceAudio,
    channels_text,
    format_duration,
    format_size,
    get_format,
    get_quality,
    plan_encoding,
    reduction_percent,
    suggest_output_path,
    with_extension,
)
from modules.mod_02_convert.services._02_service_convert import ConvertService
from modules.mod_02_convert.services._02_service_probe import ProbeService
from modules.mod_02_convert.workers._02_worker_convert import ConvertWorker
from modules.mod_02_convert.workers._02_worker_probe import ProbeWorker

PERCENT = 100


class ConvertCoordinator(QObject):
    """
    Coordinador del modulo Convertir.

    Responsabilidades
    -----------------
    1. Leer el video elegido (ffmpeg -i) en un hilo y decidir el plan de audio.
    2. Proponer la ruta de salida y mantenerla al dia con el formato.
    3. Lanzar la conversion, informar el avance y permitir cancelarla.
    4. Recordar el formato y la calidad elegidos (``app_settings.json``).

    SEÑALES
    -------
    state_changed(dict)   -> payload de la maquina de estados
    source_changed(dict)  -> name, info (vacio si no hay video)
    plan_changed(dict)    -> estimate, detail, copy
    output_changed(str)   -> ruta de salida propuesta
    progress(int)         -> 0..100
    converted(dict)       -> ok, message, summary, output_path, cancelled
    """

    state_changed = Signal(object)
    source_changed = Signal(object)
    plan_changed = Signal(object)
    output_changed = Signal(str)
    progress = Signal(int)
    converted = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        save_config: Callable[[AppConfig], bool] = save_app_config,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._save_config = save_config  # las pruebas pasan uno que no escribe en disco
        self.logic = ConvertLogic()
        self._probe_service = ProbeService(debug=config.debug)
        self._convert_service = ConvertService(debug=config.debug)

        self._input_path = ""
        self._source: SourceAudio | None = None
        self._plan: EncodePlan | None = None
        self._output_path = ""
        self._output_dir = ""  # carpeta elegida a mano: se conserva al cambiar de video
        self._format_key = get_format(config.audio_format).key
        self._quality_key = get_quality(config.quality).value

        # Referencias a hilos y workers: sin ellas Python podria liberarlos en plena ejecucion.
        self._probe_thread: QThread | None = None
        self._probe_worker: ProbeWorker | None = None
        self._probe_requests = RequestSequence()
        self._probe_pending = ""  # un video pedido mientras el hilo anterior seguia vivo
        self._convert_thread: QThread | None = None
        self._convert_worker: ConvertWorker | None = None
        self._convert_requests = RequestSequence()
        self._stop_event: threading.Event | None = None

    # -- Opciones para la interfaz -----------------------------

    @staticmethod
    def formats() -> list[tuple[str, str, str]]:
        return [(fmt.key, fmt.label, fmt.tip) for fmt in FORMATS]

    @staticmethod
    def qualities() -> list[tuple[str, str, str]]:
        return [(q.key.value, q.label, q.tip) for q in QUALITIES]

    @property
    def format_key(self) -> str:
        return self._format_key

    @property
    def quality_key(self) -> str:
        return self._quality_key

    @property
    def last_input_dir(self) -> str:
        return self._config.last_input_dir

    @property
    def output_path(self) -> str:
        return self._output_path

    def output_filter(self) -> str:
        fmt = get_format(self._format_key)
        return f"{fmt.label} (*{fmt.extension})"

    # -- API publica -------------------------------------------

    def select_input(self, path: str) -> None:
        """Lee el video ``path`` en un hilo; el resultado llega por ``source_changed``."""
        path = path.strip()
        if not path:
            return
        payload = self.logic.select_input()
        self.state_changed.emit(payload)
        if not payload["ok"]:
            return
        self._input_path = path
        self._source = None
        self._plan = None
        self.source_changed.emit({"name": Path(path).name, "info": "Leyendo el video..."})
        if self._probe_thread is not None:
            # Un solo hilo vivo por flujo: se arranca al limpiar el anterior.
            self._probe_requests.next()
            self._probe_pending = path
            return
        self._launch_probe(path)

    def set_format(self, key: str) -> None:
        self._format_key = get_format(key).key
        self._config.audio_format = self._format_key
        self._save_config(self._config)
        if self._output_path:
            self._set_output(with_extension(self._output_path, get_format(key).extension))
        self._update_plan()

    def set_quality(self, key: str) -> None:
        self._quality_key = get_quality(key).value
        self._config.quality = self._quality_key
        self._save_config(self._config)
        self._update_plan()

    def set_output_path(self, path: str) -> None:
        """Ruta escrita o elegida por el usuario; su carpeta se conserva para el siguiente video."""
        path = path.strip()
        if not path or path == self._output_path:
            return
        self._output_dir = str(Path(path).parent)
        extension = get_format(self._format_key).extension
        self._set_output(path if Path(path).suffix else path + extension)

    def output_exists(self) -> bool:
        return bool(self._output_path) and Path(self._output_path).exists()

    def start_convert(self) -> None:
        if self._source is None or self._plan is None or not self._output_path:
            return
        payload = self.logic.start_convert()
        self.state_changed.emit(payload)
        if not payload["ok"]:
            return
        self.progress.emit(0)
        self._stop_event = threading.Event()
        job = {
            "input_path": self._input_path,
            "output_path": self._output_path,
            "duration_s": self._source.duration_s,
        }
        worker = self._convert_worker = ConvertWorker(
            service=self._convert_service,
            job=job,
            plan=self._plan,
            request_id=self._convert_requests.next(),
            should_stop=self._stop_event.is_set,
        )
        worker.progress.connect(self._on_progress)
        self._convert_thread = start_worker(
            self, worker, on_done=self._on_converted, on_cleared=self._clear_convert_refs
        )

    def cancel(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def close(self) -> None:
        """Libera hilos; la UI lo llama en su closeEvent."""
        self.cancel()
        stop_thread(self._convert_thread)
        stop_thread(self._probe_thread)
        self.logic.reset()

    # -- Lectura del video -------------------------------------

    def _launch_probe(self, path: str) -> None:
        worker = self._probe_worker = ProbeWorker(
            self._probe_service, path, self._probe_requests.next()
        )
        self._probe_thread = start_worker(
            self, worker, on_done=self._on_probed, on_cleared=self._clear_probe_refs
        )

    def _on_probed(self, payload: object) -> None:
        if not self._probe_requests.is_current(payload):
            return
        source: SourceAudio | None = payload.get("source")
        has_audio = bool(source and source.has_audio)
        state = self.logic.finish_probe(bool(payload["ok"]), has_audio, payload["message"])
        name = Path(payload["input_path"]).name
        if not state["ok"]:
            self.source_changed.emit({"name": name, "info": ""})
            self.state_changed.emit(state)
            return
        self._source = source
        self._config.last_input_dir = str(Path(payload["input_path"]).parent)
        self._save_config(self._config)
        self.source_changed.emit({"name": name, "info": self._source_text(source)})
        extension = get_format(self._format_key).extension
        self._set_output(suggest_output_path(payload["input_path"], extension, self._output_dir))
        self._update_plan()
        self.state_changed.emit(state)

    def _clear_probe_refs(self) -> None:
        self._probe_thread = None
        self._probe_worker = None
        if self._probe_pending:
            path, self._probe_pending = self._probe_pending, ""
            self._launch_probe(path)

    # -- Conversion --------------------------------------------

    def _on_progress(self, fraction: float) -> None:
        self.progress.emit(round(fraction * PERCENT))

    def _on_converted(self, payload: object) -> None:
        if not self._convert_requests.is_current(payload):
            return
        state = self.logic.finish_convert(
            ok=bool(payload.get("ok")),
            message=str(payload.get("message", "")),
            cancelled=bool(payload.get("cancelled")),
        )
        summary = ""
        if payload.get("ok") and self._source is not None:
            before, after = self._source.size_bytes, int(payload.get("output_bytes", 0))
            summary = (
                f"{format_size(before)} → {format_size(after)} · "
                f"{reduction_percent(before, after)} % menos"
            )
        self.state_changed.emit(state)
        self.converted.emit(
            {
                "ok": bool(payload.get("ok")),
                "cancelled": bool(payload.get("cancelled")),
                "message": state["message"],
                "summary": summary,
                "output_path": payload.get("output_path", ""),
            }
        )

    def _clear_convert_refs(self) -> None:
        self._convert_thread = None
        self._convert_worker = None
        self._stop_event = None

    # -- Helpers -----------------------------------------------

    def _set_output(self, path: str) -> None:
        self._output_path = path
        self.output_changed.emit(path)

    def _update_plan(self) -> None:
        if self._source is None:
            return
        self._plan = plan_encoding(self._source, self._format_key, self._quality_key)
        plan, fmt = self._plan, get_format(self._format_key)
        if plan.copy:
            detail = f"{fmt.label} {plan.kbps} kb/s {channels_text(plan.channels)}, sin recodificar"
        else:
            detail = f"{fmt.label} {plan.kbps} kb/s {channels_text(plan.channels)}"
        percent = reduction_percent(self._source.size_bytes, plan.estimated_bytes)
        self.plan_changed.emit(
            {
                "estimate": f"≈ {format_size(plan.estimated_bytes)} · {percent} % menos",
                "detail": detail,
                "copy": plan.copy,
            }
        )

    @staticmethod
    def _source_text(source: SourceAudio) -> str:
        parts = [format_duration(source.duration_s), format_size(source.size_bytes)]
        audio = f"{source.codec.upper()} {channels_text(source.channels)}"
        if source.bitrate_kbps:
            audio += f" {source.bitrate_kbps} kb/s"
        parts.append(audio)
        return " · ".join(parts)

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from modules.mod_02_convert.services._02_service_convert import ConvertService

logger = logging.getLogger(__name__)


class ConvertWorker(QObject):
    """
    Corre ``ConvertService.convert`` en un hilo secundario.

    SEÑALES
    -------
    progress(float)  -> de 0.0 a 1.0
    finished(dict)
        _request_id  : int
        ok           : bool
        message      : str
        cancelled    : bool
        output_path  : str
        output_bytes : int
        elapsed_s    : float
    """

    progress = Signal(float)
    finished = Signal(object)

    def __init__(
        self,
        service: ConvertService,
        job: dict,
        plan: object,  # EncodePlan: el worker solo lo pasa al servicio
        request_id: int,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._job = job
        self._plan = plan
        self._request_id = request_id
        self._should_stop = should_stop

    @Slot()
    def run(self) -> None:
        payload = {"_request_id": self._request_id, "cancelled": False}
        try:
            result = self._service.convert(
                self._job["input_path"],
                self._job["output_path"],
                self._plan,
                self._job["duration_s"],
                on_progress=self.progress.emit,
                should_stop=self._should_stop,
            )
            payload.update(
                ok=result.ok,
                message=result.message,
                cancelled=result.cancelled,
                output_path=result.output_path,
                output_bytes=result.output_bytes,
                elapsed_s=result.elapsed_s,
            )
        except Exception:
            # Frontera del hilo: sin esto el boton quedaria en Cancelar para siempre.
            logger.exception("Fallo inesperado en %s", type(self).__name__)
            payload.update(ok=False, message="Error inesperado. Revisa el log.")
        self.finished.emit(payload)

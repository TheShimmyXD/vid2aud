from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from modules.mod_02_convert.services._02_service_probe import ProbeService

logger = logging.getLogger(__name__)


class ProbeWorker(QObject):
    """
    Lee el video con ``ProbeService.probe`` fuera del hilo de la interfaz.

    SEÑALES
    -------
    finished(dict)
        _request_id : int
        ok          : bool
        message     : str
        source      : SourceAudio | None
        input_path  : str
    """

    finished = Signal(object)

    def __init__(self, service: ProbeService, input_path: str, request_id: int) -> None:
        super().__init__()
        self._service = service
        self._input_path = input_path
        self._request_id = request_id

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.probe(self._input_path)
            ok, message, source = result.ok, result.message, result.source
        except Exception:
            # Frontera del hilo: una excepcion aqui mataria el worker sin avisar a la UI.
            logger.exception("Fallo inesperado en %s", type(self).__name__)
            ok, message, source = False, "Error inesperado. Revisa el log.", None
        self.finished.emit(
            {
                "_request_id": self._request_id,
                "ok": ok,
                "message": message,
                "source": source,
                "input_path": self._input_path,
            }
        )

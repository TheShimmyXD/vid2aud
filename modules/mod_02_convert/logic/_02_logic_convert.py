from __future__ import annotations

from enum import StrEnum


class ConvertState(StrEnum):
    EMPTY = "EMPTY"  # sin video elegido
    PROBING = "PROBING"  # ffmpeg esta leyendo el video
    READY = "READY"  # video con audio, listo para convertir
    INVALID = "INVALID"  # el archivo no se puede convertir (sin audio, no es video)
    CONVERTING = "CONVERTING"  # conversion en curso en un hilo secundario
    DONE = "DONE"  # la ultima conversion termino bien
    ERROR = "ERROR"  # la ultima conversion fallo


class ConvertLogic:
    """
    MAQUINA DE ESTADOS - MODULO CONVERTIR

    EMPTY / READY / INVALID / DONE / ERROR
        -> select_input()                    -> PROBING
    PROBING
        -> select_input()                    -> PROBING (el resultado viejo se descarta)
        -> finish_probe(ok, has_audio)       -> READY
        -> finish_probe(ok=False | sin audio) -> INVALID
    READY / DONE / ERROR
        -> start_convert()                   -> CONVERTING
    CONVERTING
        -> finish_convert(ok=True)           -> DONE
        -> finish_convert(ok=False)          -> ERROR
        -> finish_convert(cancelled)         -> READY
    CUALQUIERA salvo CONVERTING
        -> clear()                           -> EMPTY

    REGLAS
    - Sin PySide6 ni E/S: solo transiciones y textos.
    - Mientras convierte no se cambia el video (el boton queda en Cancelar).
    """

    def __init__(self) -> None:
        self.state = ConvertState.EMPTY
        self._message = ""

    @property
    def is_busy(self) -> bool:
        return self.state in (ConvertState.PROBING, ConvertState.CONVERTING)

    @property
    def can_convert(self) -> bool:
        return self.state in (ConvertState.READY, ConvertState.DONE, ConvertState.ERROR)

    @property
    def can_change_input(self) -> bool:
        return self.state is not ConvertState.CONVERTING

    # -- Transiciones ------------------------------------------

    def select_input(self) -> dict:
        if not self.can_change_input:
            return self._payload(ok=False, message="Espera a que termine la conversión.")
        self.state = ConvertState.PROBING
        return self._payload(ok=True, message="")

    def finish_probe(self, ok: bool, has_audio: bool, message: str = "") -> dict:
        if self.state is not ConvertState.PROBING:
            return self._payload(ok=False, message="")
        if ok and has_audio:
            self.state = ConvertState.READY
            return self._payload(ok=True, message="")
        self.state = ConvertState.INVALID
        if ok:
            message = "Este video no tiene pista de audio."
        return self._payload(ok=False, message=message or "No se pudo leer el archivo.")

    def start_convert(self) -> dict:
        if not self.can_convert:
            return self._payload(ok=False, message="Primero elige un video con audio.")
        self.state = ConvertState.CONVERTING
        return self._payload(ok=True, message="")

    def finish_convert(self, ok: bool, message: str = "", cancelled: bool = False) -> dict:
        if self.state is not ConvertState.CONVERTING:
            return self._payload(ok=False, message="")
        if cancelled:
            self.state = ConvertState.READY
            return self._payload(ok=True, message="Conversión cancelada.")
        if ok:
            self.state = ConvertState.DONE
            return self._payload(ok=True, message=message)
        self.state = ConvertState.ERROR
        return self._payload(ok=False, message=message or "La conversión falló.")

    def clear(self) -> dict:
        if not self.can_change_input:
            return self._payload(ok=False, message="Espera a que termine la conversión.")
        self.state = ConvertState.EMPTY
        return self._payload(ok=True, message="")

    def reset(self) -> None:
        self.state = ConvertState.EMPTY
        self._message = ""

    # -- Helpers -----------------------------------------------

    def _payload(self, ok: bool, message: str) -> dict:
        self._message = message
        return {
            "ok": ok,
            "state": self.state.value,
            "status": message,
            "message": message,
            "can_convert": self.can_convert,
            "busy": self.is_busy,
        }

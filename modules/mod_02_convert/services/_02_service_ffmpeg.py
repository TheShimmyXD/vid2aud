"""Responsabilidad unica: encontrar el ejecutable de ffmpeg.

Primero el del sistema (si el usuario lo instala, manda ese); si no hay, el que
trae el paquete ``imageio-ffmpeg`` dentro del ``.venv``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}

# En Windows, que ffmpeg no abra una consola encima de la ventana; en Linux vale 0.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_ffmpeg() -> str:
    """Ruta de ffmpeg o cadena vacia si no hay ninguno."""
    if "path" in _cache:
        return _cache["path"]
    path = shutil.which("ffmpeg") or ""
    if not path:
        try:
            import imageio_ffmpeg

            path = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError) as exc:
            logger.error("No hay ffmpeg en el sistema ni en imageio-ffmpeg: %s", exc)
            path = ""
    if path:
        logger.info("ffmpeg: %s", path)
    _cache["path"] = path
    return path

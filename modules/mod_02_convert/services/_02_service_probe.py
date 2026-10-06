"""Responsabilidad unica: leer con ffmpeg que audio trae un video.

No se usa ffprobe (no viene en ``imageio-ffmpeg``): se corre ``ffmpeg -i`` sin
salida y se lee el resumen que escribe en stderr. El formato de ese resumen
sale de muestras reales guardadas en ``tests/fixtures/ffmpeg/`` (regla 1).
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from logging_config import level_from_debug
from modules.mod_02_convert.logic._02_logic_presets import SourceAudio
from modules.mod_02_convert.services._02_service_ffmpeg import NO_WINDOW, find_ffmpeg

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 30
RX_DURATION = re.compile(r"Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
RX_AUDIO = re.compile(r"Stream #\d+:\d+\S*: Audio: (?P<codec>\w+)(?P<rest>.*)")
RX_RATE = re.compile(r"(\d+) Hz")
RX_KBPS = re.compile(r"(\d+) kb/s")
RX_TITLE = re.compile(r"^\s{4}title\s*: (.+)$", re.MULTILINE)
RX_CHANNELS = re.compile(r"(\d+) channels")
LAYOUT_CHANNELS = {"mono": 1, "stereo": 2, "2.1": 3, "quad": 4, "5.0": 5, "5.1": 6, "7.1": 8}
NOT_FOUND = "No such file or directory"
INPUT_ERROR = "Error opening input"


@dataclass(slots=True)
class ProbeResult:
    ok: bool
    message: str
    source: SourceAudio | None = None


def parse_probe(text: str, size_bytes: int) -> ProbeResult:
    """El resumen de ``ffmpeg -i`` -> ``SourceAudio``; ``ok=False`` si no es un medio."""
    if NOT_FOUND in text:
        return ProbeResult(False, "El archivo no existe.")
    if INPUT_ERROR in text or "Input #0" not in text:
        return ProbeResult(False, "No parece un video: ffmpeg no lo pudo abrir.")

    duration = 0.0
    match = RX_DURATION.search(text)
    if match:
        hours, minutes, seconds = match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    title_match = RX_TITLE.search(text)
    title = title_match.group(1).strip() if title_match else ""

    audio = RX_AUDIO.search(text)
    if audio is None:
        source = SourceAudio(duration, size_bytes, has_audio=False, title=title)
        return ProbeResult(True, "", source)

    rest = audio.group("rest")
    rate = RX_RATE.search(rest)
    kbps = RX_KBPS.search(rest)
    source = SourceAudio(
        duration_s=duration,
        size_bytes=size_bytes,
        has_audio=True,
        codec=audio.group("codec"),
        channels=_channels(rest),
        sample_rate=int(rate.group(1)) if rate else 0,
        bitrate_kbps=int(kbps.group(1)) if kbps else None,
        title=title,
    )
    return ProbeResult(True, "", source)


def _channels(rest: str) -> int:
    """Canales a partir del texto despues del codec (``48000 Hz, stereo, fltp``)."""
    fields = [field.strip() for field in rest.split(",")]
    for field in fields:
        layout = field.split("(")[0]
        if layout in LAYOUT_CHANNELS:
            return LAYOUT_CHANNELS[layout]
    match = RX_CHANNELS.search(rest)
    return int(match.group(1)) if match else 2


class ProbeService:
    """Corre ``ffmpeg -i`` sobre un archivo y devuelve lo que trae."""

    def __init__(self, debug: bool = False) -> None:
        logger.setLevel(level_from_debug(debug))

    def probe(self, input_path: str) -> ProbeResult:
        """Nunca lanza: los errores esperables vuelven con ``ok=False``."""
        path = Path(input_path)
        if not path.is_file():
            return ProbeResult(False, "El archivo no existe.")
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return ProbeResult(False, "No se encontró ffmpeg. Reinstala las dependencias.")
        try:
            done = subprocess.run(
                [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PROBE_TIMEOUT_S,
                check=False,
                creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("ffmpeg -i fallo sobre %s: %s", path.name, exc)
            return ProbeResult(False, "ffmpeg no pudo leer el archivo.")
        result = parse_probe(done.stderr, path.stat().st_size)
        logger.info("Lectura de %s: %s", path.name, result.source or result.message)
        return result

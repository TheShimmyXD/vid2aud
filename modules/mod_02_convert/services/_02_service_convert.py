"""Responsabilidad unica: escribir el audio de un video con ffmpeg.

La salida va primero a ``<salida>.part`` y solo al terminar bien se renombra:
nunca queda un audio a medias con el nombre final, y el video de entrada no se
toca (regla 3). El avance se lee de ``-progress pipe:1`` (muestra real en
``tests/fixtures/ffmpeg/progress_opus.txt``).
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from logging_config import level_from_debug
from modules.mod_02_convert.logic._02_logic_presets import EncodePlan
from modules.mod_02_convert.services._02_service_ffmpeg import NO_WINDOW, find_ffmpeg

logger = logging.getLogger(__name__)

PART_SUFFIX = ".part"
TERMINATE_WAIT_S = 5
STDERR_TAIL = 400
MICROSECONDS = 1_000_000


@dataclass(slots=True)
class ConvertResult:
    ok: bool
    message: str
    output_path: str = ""
    output_bytes: int = 0
    elapsed_s: float = 0.0
    cancelled: bool = False


def part_path(output_path: str) -> Path:
    path = Path(output_path)
    return path.with_name(path.name + PART_SUFFIX)


def build_command(ffmpeg: str, input_path: str, output_part: str, plan: EncodePlan) -> list[str]:
    """La orden completa: solo la primera pista de audio, con sus metadatos."""
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_path,
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-map_metadata",
        "0",
        "-c:a",
        plan.encoder,
    ]
    if not plan.copy:
        command += [*plan.encoder_args, "-b:a", f"{plan.kbps}k", "-ac", str(plan.channels)]
    command += [*plan.muxer_args, "-f", plan.muxer, "-progress", "pipe:1", "-nostats"]
    command.append(output_part)
    return command


def parse_progress_line(line: str) -> float | None:
    """Segundos ya escritos si la linea es ``out_time_us=...``; si no, ``None``."""
    key, _, value = line.strip().partition("=")
    if key != "out_time_us":
        return None
    try:
        return max(int(value), 0) / MICROSECONDS
    except ValueError:
        return None


class ConvertService:
    """Convierte un video a audio con un ``EncodePlan`` ya decidido."""

    def __init__(self, debug: bool = False) -> None:
        logger.setLevel(level_from_debug(debug))

    def convert(
        self,
        input_path: str,
        output_path: str,
        plan: EncodePlan,
        duration_s: float,
        on_progress: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> ConvertResult:
        """Nunca lanza por errores esperables; ``on_progress`` recibe de 0.0 a 1.0."""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return ConvertResult(False, "No se encontró ffmpeg. Reinstala las dependencias.")
        if Path(output_path).resolve() == Path(input_path).resolve():
            return ConvertResult(False, "La salida no puede ser el mismo video.")
        part = part_path(output_path)
        command = build_command(ffmpeg, input_path, str(part), plan)
        logger.info("Conversion: %s", " ".join(command[1:]))
        started = time.monotonic()
        try:
            part.parent.mkdir(parents=True, exist_ok=True)
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=NO_WINDOW,
            )
        except OSError as exc:
            logger.exception("No se pudo iniciar ffmpeg")
            return ConvertResult(False, f"No se pudo iniciar ffmpeg: {exc}")

        cancelled = self._follow(process, duration_s, on_progress, should_stop)
        stderr = process.stderr.read() if process.stderr else ""
        returncode = process.wait()
        elapsed = time.monotonic() - started

        if cancelled or returncode != 0:
            part.unlink(missing_ok=True)
            if cancelled:
                return ConvertResult(False, "Conversión cancelada.", cancelled=True)
            logger.error("ffmpeg salio con %s: %s", returncode, stderr[-STDERR_TAIL:])
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else ""
            return ConvertResult(False, f"ffmpeg no pudo convertir el video. {detail}".strip())

        try:
            part.replace(output_path)
        except OSError as exc:
            part.unlink(missing_ok=True)
            return ConvertResult(False, f"No se pudo guardar el audio: {exc}")
        size = Path(output_path).stat().st_size
        if on_progress:
            on_progress(1.0)
        logger.info("Audio listo: %s (%s bytes, %.1f s)", output_path, size, elapsed)
        return ConvertResult(True, "Listo.", output_path, size, elapsed)

    def _follow(
        self,
        process: subprocess.Popen,
        duration_s: float,
        on_progress: Callable[[float], None] | None,
        should_stop: Callable[[], bool] | None,
    ) -> bool:
        """Lee el avance hasta que ffmpeg termina; devuelve True si se cancelo."""
        assert process.stdout is not None
        for line in process.stdout:
            if should_stop and should_stop():
                process.terminate()
                try:
                    process.wait(TERMINATE_WAIT_S)
                except subprocess.TimeoutExpired:
                    process.kill()
                return True
            seconds = parse_progress_line(line)
            if seconds is not None and on_progress and duration_s > 0:
                on_progress(min(seconds / duration_s, 1.0))
        return False

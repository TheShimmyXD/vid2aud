"""Formatos de audio, calidades y el plan de codificacion.

Codigo puro: recibe lo que se sabe del audio del video (``SourceAudio``) y la
eleccion del usuario, y devuelve un ``EncodePlan`` con todo lo que el servicio
necesita para armar la orden de ffmpeg. Un formato nuevo se agrega solo en
``FORMATS``; nadie mas pregunta por el tipo de formato.

Reglas del plan:
- Nunca mas canales que el original; 5.1 o 7.1 bajan a estereo; Voz va en mono.
- Nunca mas bitrate que el original (si se conoce): subirlo solo agranda el archivo.
- Si el original ya viene en el codec elegido y no supera el objetivo, se copia
  tal cual (sin recodificar: cero perdida y casi instantaneo).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

# Sobrecosto aproximado del contenedor sobre el audio puro (cabeceras, paginas Ogg).
CONTAINER_OVERHEAD = 1.01
BYTES_PER_KILOBIT = 125  # 1000 bits / 8
VOICE_CHANNELS = 1
MAX_CHANNELS = 2


class Quality(StrEnum):
    VOICE = "voice"  # clases, podcasts, reuniones: mono y muy liviano
    BALANCED = "balanced"  # musica y video en general: la recomendada
    HIGH = "high"  # musica exigente


@dataclass(frozen=True, slots=True)
class QualityInfo:
    key: Quality
    label: str
    tip: str


QUALITIES: tuple[QualityInfo, ...] = (
    QualityInfo(
        Quality.VOICE,
        "Voz",
        "Clases, podcasts y reuniones: mono y lo más liviano posible.",
    ),
    QualityInfo(
        Quality.BALANCED,
        "Equilibrada",
        "Música y video en general: no se nota la diferencia con el original.",
    ),
    QualityInfo(
        Quality.HIGH,
        "Alta",
        "Para música que se escucha con buenos audífonos.",
    ),
)


@dataclass(frozen=True, slots=True)
class AudioFormat:
    """Un formato de salida: codec, contenedor y bitrate por calidad.

    ``kbps`` guarda, por calidad, el par (estereo, mono) en kb/s.
    """

    key: str
    label: str
    tip: str
    extension: str
    encoder: str  # nombre del codificador en ffmpeg
    codec: str  # nombre con el que ffmpeg lo reporta al leer un archivo
    muxer: str  # contenedor (-f): la salida se escribe a un .part
    kbps: dict[Quality, tuple[int, int]]
    encoder_args: tuple[str, ...] = ()
    muxer_args: tuple[str, ...] = ()


FORMATS: tuple[AudioFormat, ...] = (
    AudioFormat(
        key="opus",
        label="Opus",
        tip=(
            "El más liviano a igual calidad. Suena en VLC, Android, WhatsApp, "
            "navegadores y casi cualquier reproductor moderno."
        ),
        extension=".opus",
        encoder="libopus",
        codec="opus",
        muxer="opus",
        kbps={
            Quality.VOICE: (32, 32),
            Quality.BALANCED: (96, 64),
            Quality.HIGH: (128, 80),
        },
        encoder_args=("-vbr", "on"),
    ),
    AudioFormat(
        key="aac",
        label="AAC",
        tip="Archivo .m4a: compatible con todo, también iPhone, iTunes y el carro.",
        extension=".m4a",
        encoder="aac",
        codec="aac",
        muxer="ipod",
        kbps={
            Quality.VOICE: (64, 64),
            Quality.BALANCED: (128, 80),
            Quality.HIGH: (192, 112),
        },
        muxer_args=("-movflags", "+faststart"),
    ),
    AudioFormat(
        key="mp3",
        label="MP3",
        tip="El universal: suena hasta en equipos viejos, pero pesa más.",
        extension=".mp3",
        encoder="libmp3lame",
        codec="mp3",
        muxer="mp3",
        kbps={
            Quality.VOICE: (64, 64),
            Quality.BALANCED: (128, 96),
            Quality.HIGH: (192, 128),
        },
        encoder_args=("-abr", "1"),
        muxer_args=("-id3v2_version", "3"),
    ),
)

DEFAULT_FORMAT = "opus"
DEFAULT_QUALITY = Quality.BALANCED


@dataclass(frozen=True, slots=True)
class SourceAudio:
    """Lo que ffmpeg dice del video: duracion, peso y su primera pista de audio."""

    duration_s: float
    size_bytes: int
    has_audio: bool
    codec: str = ""
    channels: int = 0
    sample_rate: int = 0
    bitrate_kbps: int | None = None  # algunos contenedores (mkv) no lo reportan
    title: str = ""


@dataclass(frozen=True, slots=True)
class EncodePlan:
    """Como se va a escribir el audio: lo lee el servicio para armar la orden."""

    format_key: str
    extension: str
    encoder: str
    muxer: str
    kbps: int
    channels: int
    copy: bool
    estimated_bytes: int
    encoder_args: tuple[str, ...] = ()
    muxer_args: tuple[str, ...] = ()


def get_format(key: str) -> AudioFormat:
    """El formato ``key``; uno desconocido cae en el de por defecto."""
    by_key = {fmt.key: fmt for fmt in FORMATS}
    return by_key.get(key, by_key[DEFAULT_FORMAT])


def get_quality(key: str) -> Quality:
    try:
        return Quality(key)
    except ValueError:
        return DEFAULT_QUALITY


def plan_encoding(source: SourceAudio, format_key: str, quality_key: str) -> EncodePlan:
    """El plan para convertir ``source`` al formato y la calidad elegidos."""
    fmt = get_format(format_key)
    quality = get_quality(quality_key)
    limit = VOICE_CHANNELS if quality is Quality.VOICE else MAX_CHANNELS
    channels = max(1, min(source.channels or limit, limit))
    stereo_kbps, mono_kbps = fmt.kbps[quality]
    kbps = mono_kbps if channels == 1 else stereo_kbps
    if source.bitrate_kbps:
        kbps = min(kbps, source.bitrate_kbps)

    copy = (
        source.codec == fmt.codec
        and source.bitrate_kbps is not None
        and source.bitrate_kbps <= kbps
        and source.channels <= channels
    )
    if copy:
        kbps = source.bitrate_kbps or kbps
        channels = source.channels
    return EncodePlan(
        format_key=fmt.key,
        extension=fmt.extension,
        encoder="copy" if copy else fmt.encoder,
        muxer=fmt.muxer,
        kbps=kbps,
        channels=channels,
        copy=copy,
        estimated_bytes=estimate_bytes(kbps, source.duration_s),
        encoder_args=() if copy else fmt.encoder_args,
        muxer_args=fmt.muxer_args,
    )


def estimate_bytes(kbps: int, duration_s: float) -> int:
    return round(kbps * BYTES_PER_KILOBIT * max(duration_s, 0.0) * CONTAINER_OVERHEAD)


def suggest_output_path(input_path: str, extension: str, folder: str = "") -> str:
    """Mismo nombre que el video con la extension del audio, en ``folder`` o junto al video."""
    source = PurePath(input_path)
    target_dir = PurePath(folder) if folder else source.parent
    return str(target_dir / f"{source.stem}{extension}")


def with_extension(output_path: str, extension: str) -> str:
    """Cambia la extension de una salida ya elegida (al cambiar de formato)."""
    path = PurePath(output_path)
    return str(path.with_suffix(extension)) if path.name else output_path


# -- Textos para la interfaz (sin Qt) ----------------------------

SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")
UNIT_STEP = 1024


def format_size(size_bytes: int) -> str:
    size = float(max(size_bytes, 0))
    for unit in SIZE_UNITS:
        if size < UNIT_STEP or unit == SIZE_UNITS[-1]:
            decimals = 0 if unit in ("B", "KB") or size >= 100 else 1
            return f"{size:.{decimals}f} {unit}".replace(".", ",")
        size /= UNIT_STEP
    return ""


def format_duration(seconds: float) -> str:
    total = round(max(seconds, 0.0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


def channels_text(channels: int) -> str:
    names = {1: "mono", 2: "estéreo", 6: "5.1", 8: "7.1"}
    return names.get(channels, f"{channels} canales")


def reduction_percent(before_bytes: int, after_bytes: int) -> int:
    """Cuanto menos pesa el audio que el video, en porciento entero."""
    if before_bytes <= 0:
        return 0
    return round(100 * (1 - after_bytes / before_bytes))

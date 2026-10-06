"""El parser de ``ffmpeg -i`` contra salidas reales del ffmpeg empaquetado (2026-10-05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.mod_02_convert.services._02_service_probe import parse_probe

FIXTURES = Path(__file__).parent / "fixtures" / "ffmpeg"


def _probe(name: str):
    return parse_probe((FIXTURES / name).read_text(encoding="utf-8"), size_bytes=1000)


def test_mp4_with_aac_stereo():
    result = _probe("probe_clip_aac.txt")
    source = result.source
    assert result.ok and source is not None
    assert source.has_audio
    assert (source.codec, source.channels, source.sample_rate) == ("aac", 2, 48000)
    assert source.bitrate_kbps == 191
    assert source.duration_s == pytest.approx(20.0)
    assert source.title == "Prueba"


def test_mkv_flac_surround_without_bitrate():
    source = _probe("probe_clip_flac51.txt").source
    assert source is not None
    assert (source.codec, source.channels, source.sample_rate) == ("flac", 6, 44100)
    assert source.bitrate_kbps is None
    assert source.duration_s == pytest.approx(8.0)


def test_mono_aac():
    source = _probe("probe_clip_mono.txt").source
    assert source is not None
    assert (source.channels, source.bitrate_kbps, source.sample_rate) == (1, 62, 22050)


def test_video_without_audio():
    result = _probe("probe_clip_noaudio.txt")
    assert result.ok
    assert result.source is not None and not result.source.has_audio
    assert result.source.duration_s == pytest.approx(3.0)


def test_not_a_media_file():
    result = _probe("probe_not_media.txt")
    assert not result.ok
    assert "video" in result.message


def test_missing_file():
    result = _probe("probe_missing.txt")
    assert not result.ok
    assert "no existe" in result.message

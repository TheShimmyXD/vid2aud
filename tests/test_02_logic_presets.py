from __future__ import annotations

import pytest

from modules.mod_02_convert.logic._02_logic_presets import (
    FORMATS,
    QUALITIES,
    Quality,
    SourceAudio,
    estimate_bytes,
    format_duration,
    format_size,
    get_format,
    plan_encoding,
    reduction_percent,
    suggest_output_path,
    with_extension,
)

HOUR = 3600.0


def _source(**changes) -> SourceAudio:
    base = dict(
        duration_s=HOUR,
        size_bytes=1_500_000_000,
        has_audio=True,
        codec="aac",
        channels=2,
        sample_rate=48000,
        bitrate_kbps=192,
    )
    base.update(changes)
    return SourceAudio(**base)


def test_every_format_has_every_quality():
    for fmt in FORMATS:
        assert set(fmt.kbps) == {q.key for q in QUALITIES}
        assert fmt.extension.startswith(".")


def test_default_is_opus_balanced_stereo():
    plan = plan_encoding(_source(), "opus", "balanced")
    assert (plan.encoder, plan.kbps, plan.channels, plan.copy) == ("libopus", 96, 2, False)
    assert plan.extension == ".opus"


def test_unknown_keys_fall_back_to_defaults():
    plan = plan_encoding(_source(), "flac?", "loud?")
    assert plan.format_key == "opus"
    assert plan.kbps == 96


def test_voice_forces_mono():
    plan = plan_encoding(_source(), "opus", Quality.VOICE)
    assert plan.channels == 1
    assert plan.kbps == 32


def test_surround_goes_down_to_stereo():
    plan = plan_encoding(_source(channels=6, codec="flac", bitrate_kbps=None), "aac", "high")
    assert plan.channels == 2
    assert plan.kbps == 192


def test_mono_source_stays_mono_with_mono_rate():
    plan = plan_encoding(_source(channels=1, bitrate_kbps=None, codec="flac"), "opus", "high")
    assert plan.channels == 1
    assert plan.kbps == 80


def test_never_more_bitrate_than_the_source():
    plan = plan_encoding(_source(codec="ac3", bitrate_kbps=48), "mp3", "high")
    assert plan.kbps == 48


def test_same_codec_not_above_target_is_copied():
    plan = plan_encoding(_source(bitrate_kbps=128), "aac", "balanced")
    assert plan.copy
    assert plan.encoder == "copy"
    assert plan.encoder_args == ()


def test_same_codec_above_target_is_reencoded():
    plan = plan_encoding(_source(bitrate_kbps=256), "aac", "balanced")
    assert not plan.copy
    assert plan.kbps == 128


def test_copy_needs_known_bitrate():
    plan = plan_encoding(_source(bitrate_kbps=None), "aac", "balanced")
    assert not plan.copy


def test_estimate_is_bitrate_times_duration():
    assert estimate_bytes(96, HOUR) == pytest.approx(96 * 125 * HOUR, rel=0.02)
    plan = plan_encoding(_source(), "opus", "balanced")
    assert plan.estimated_bytes < _source().size_bytes / 20


def test_suggest_output_next_to_video_or_in_folder():
    assert suggest_output_path("/v/clase 1.mp4", ".opus") == "/v/clase 1.opus"
    assert suggest_output_path("/v/clase.mkv", ".mp3", "/audios") == "/audios/clase.mp3"


def test_with_extension_keeps_folder_and_name():
    assert with_extension("/a/b/clase.opus", ".m4a") == "/a/b/clase.m4a"
    assert with_extension("", ".m4a") == ""


def test_format_helpers():
    assert format_size(500) == "500 B"
    assert format_size(1_500_000_000) == "1,4 GB"
    assert format_size(52_000_000) == "49,6 MB"
    assert format_duration(4320) == "1 h 12 min"
    assert format_duration(75) == "1 min 15 s"
    assert reduction_percent(1000, 40) == 96
    assert reduction_percent(0, 10) == 0


def test_get_format_by_key():
    assert get_format("mp3").encoder == "libmp3lame"

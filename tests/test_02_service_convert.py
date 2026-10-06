from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.mod_02_convert.logic._02_logic_presets import SourceAudio, plan_encoding
from modules.mod_02_convert.services._02_service_convert import (
    ConvertService,
    build_command,
    parse_progress_line,
    part_path,
)
from modules.mod_02_convert.services._02_service_ffmpeg import find_ffmpeg
from modules.mod_02_convert.services._02_service_probe import ProbeService

FIXTURES = Path(__file__).parent / "fixtures" / "ffmpeg"
SOURCE = SourceAudio(10.0, 1_000_000, True, "aac", 2, 48000, 192)


def test_command_reencodes_first_audio_track_only():
    plan = plan_encoding(SOURCE, "opus", "balanced")
    command = build_command("ffmpeg", "in.mp4", "out.opus.part", plan)
    assert command[-1] == "out.opus.part"
    joined = " ".join(command)
    assert "-map 0:a:0 -vn -sn -dn" in joined
    assert "-c:a libopus -vbr on -b:a 96k -ac 2" in joined
    assert "-f opus" in joined
    assert "-progress pipe:1" in joined


def test_command_copy_has_no_bitrate():
    source = SourceAudio(10.0, 1_000_000, True, "aac", 2, 48000, 128)
    plan = plan_encoding(source, "aac", "balanced")
    command = build_command("ffmpeg", "in.mp4", "out.m4a.part", plan)
    assert "-b:a" not in command
    assert command[command.index("-c:a") + 1] == "copy"
    assert "+faststart" in command


def test_progress_lines_from_real_sample():
    lines = (FIXTURES / "progress_opus.txt").read_text(encoding="utf-8").splitlines()
    seconds = [s for s in map(parse_progress_line, lines) if s is not None]
    assert seconds == pytest.approx([13.1535, 20.010667])
    assert parse_progress_line("out_time_us=N/A") is None
    assert parse_progress_line("progress=end") is None


def test_part_path_keeps_name():
    assert part_path("/a/clase.opus") == Path("/a/clase.opus.part")


@pytest.fixture
def tiny_video(tmp_path: Path) -> Path:
    """Video real de 2 s (tono de 440 Hz) hecho con el ffmpeg del proyecto."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip("sin ffmpeg")
    video = tmp_path / "tono.mp4"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=15",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
         "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
         "-c:a", "aac", "-b:a", "192k", str(video)],
        check=True,
    )  # fmt: skip
    return video


@pytest.mark.parametrize("format_key", ["opus", "aac", "mp3"])
def test_real_conversion_is_smaller_and_leaves_no_part(tiny_video: Path, format_key: str):
    probe = ProbeService().probe(str(tiny_video))
    assert probe.ok and probe.source is not None
    plan = plan_encoding(probe.source, format_key, "balanced")
    output = tiny_video.with_suffix(plan.extension)
    progress: list[float] = []
    result = ConvertService().convert(
        str(tiny_video), str(output), plan, probe.source.duration_s, on_progress=progress.append
    )
    assert result.ok, result.message
    assert output.is_file()
    assert not part_path(str(output)).exists()
    assert 0 < result.output_bytes < tiny_video.stat().st_size
    assert progress[-1] == 1.0
    assert tiny_video.is_file()


def test_cancel_removes_partial_output(tiny_video: Path):
    probe = ProbeService().probe(str(tiny_video))
    plan = plan_encoding(probe.source, "opus", "balanced")
    output = tiny_video.with_suffix(".opus")
    result = ConvertService().convert(
        str(tiny_video), str(output), plan, 2.0, should_stop=lambda: True
    )
    assert result.cancelled
    assert not output.exists()
    assert not part_path(str(output)).exists()


def test_output_cannot_be_the_input(tiny_video: Path):
    probe = ProbeService().probe(str(tiny_video))
    plan = plan_encoding(probe.source, "aac", "balanced")
    result = ConvertService().convert(str(tiny_video), str(tiny_video), plan, 2.0)
    assert not result.ok
    assert tiny_video.is_file()

"""Humo de la pantalla Convertir: arma la ventana real y la lleva por sus estados.

Usa un video de 2 s hecho con el ffmpeg del proyecto; nada se escribe en
``resources/json`` (save_config nulo).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from config import AppConfig
from modules.mod_02_convert.logic._02_logic_convert import ConvertState
from modules.mod_02_convert.services._02_service_ffmpeg import find_ffmpeg

TIMEOUT_S = 20


def _wait(app, condition) -> bool:
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def video(tmp_path: Path) -> Path:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip("sin ffmpeg")
    path = tmp_path / "clase.mp4"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
         "-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(path)],
        check=True,
    )  # fmt: skip
    return path


@pytest.fixture
def window(qt_application):
    from ui._00_ui_main import MainWindow

    saved: list[AppConfig] = []
    win = MainWindow(config=AppConfig(theme="light"), save_config=saved.append)
    win.show()
    yield win
    win.close()


def test_empty_screen_cannot_convert(window):
    page = window._pages["convert"]
    assert not page.convert_button.isEnabled()
    assert page.drop_zone.title_label.text() == "Arrastra un video aquí"


def test_select_and_convert_real_video(qt_application, window, video: Path):
    page = window._pages["convert"]
    coordinator = page._coordinator
    page._select_input(str(video))
    assert _wait(qt_application, lambda: coordinator.logic.state is ConvertState.READY)
    assert page.output_edit.text() == str(video.with_suffix(".opus"))
    assert page.convert_button.isEnabled()
    assert "kb/s" in page.detail_label.text()

    page.format_buttons.select("mp3")
    assert page.output_edit.text().endswith(".mp3")

    page.convert_button.click()
    assert _wait(qt_application, lambda: coordinator.logic.state is ConvertState.DONE)
    assert video.with_suffix(".mp3").is_file()
    assert page.status_line.text().startswith("Listo")
    assert page.open_button.isVisibleTo(page)


def test_missing_file_is_invalid(qt_application, window, tmp_path: Path):
    page = window._pages["convert"]
    page._select_input(str(tmp_path / "no-existe.mp4"))
    coordinator = page._coordinator
    assert _wait(qt_application, lambda: coordinator.logic.state is ConvertState.INVALID)
    assert "no existe" in page.drop_zone.hint_label.text()


def test_theme_button_cycles_without_writing_disk(window):
    before = window._config.theme
    window.theme_button.click()
    assert window._config.theme != before

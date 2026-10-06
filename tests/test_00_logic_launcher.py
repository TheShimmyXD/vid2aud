from __future__ import annotations

import base64
from pathlib import Path

from logic._00_logic_launcher import (
    desktop_entry,
    encoded_command,
    launcher_paths,
    ps_quote,
    quote_exec_arg,
    shortcut_script,
    windows_launcher_paths,
)


def _fields(entry: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in entry.splitlines()[1:])


def test_paths_inside_data_home(tmp_path):
    paths = launcher_paths(tmp_path)
    assert paths.shortcut_file == tmp_path / "applications" / "vid2aud.desktop"
    assert paths.icon_file == tmp_path / "icons" / "hicolor" / "256x256" / "apps" / "vid2aud.png"


def test_plain_arg_without_quotes():
    assert quote_exec_arg("/opt/app/main.py") == "/opt/app/main.py"


def test_arg_with_space_and_dollar_is_quoted():
    assert quote_exec_arg("/mis cosas/$x.py") == '"/mis cosas/\\$x.py"'


def test_entry_fields():
    entry = desktop_entry(Path("/p/.venv/bin/python"), Path("/p/main.py"), Path("/i/vid2aud.png"))
    assert entry.startswith("[Desktop Entry]\n")
    fields = _fields(entry)
    assert fields["Type"] == "Application"
    assert fields["Exec"] == "/p/.venv/bin/python /p/main.py"
    assert fields["Path"] == "/p"
    assert fields["Icon"] == "/i/vid2aud.png"
    assert fields["Terminal"] == "false"
    assert fields["StartupWMClass"] == "vid2aud"


def test_entry_doubles_backslash_inside_quotes():
    entry = desktop_entry(Path("/a b/python"), Path("/p/main.py"), Path("/i.png"))
    assert _fields(entry)["Exec"] == '"/a b/python" /p/main.py'
    entry = desktop_entry(Path("/a\\b/python"), Path("/p/main.py"), Path("/i.png"))
    assert _fields(entry)["Exec"] == '"/a\\\\\\\\b/python" /p/main.py'


def test_windows_paths(tmp_path):
    paths = windows_launcher_paths(tmp_path / "Programs", tmp_path / "Local")
    assert paths.shortcut_file == tmp_path / "Programs" / "vid2aud.lnk"
    assert paths.icon_file == tmp_path / "Local" / "vid2aud" / "vid2aud.ico"


def test_ps_quote_doubles_single_quote():
    assert ps_quote("C:\\O'Neil\\x") == "'C:\\O''Neil\\x'"


def test_shortcut_script_fields():
    paths = windows_launcher_paths(Path("/start/Programs"), Path("/local"))
    script = shortcut_script(Path("/v/Scripts/pythonw.exe"), Path("/mis cosas/main.py"), paths)
    assert "CreateShortcut('/start/Programs/vid2aud.lnk')" in script
    assert "$link.TargetPath = '/v/Scripts/pythonw.exe'" in script
    assert """$link.Arguments = '"/mis cosas/main.py"'""" in script
    assert "$link.WorkingDirectory = '/mis cosas'" in script
    assert "$link.IconLocation = '/local/vid2aud/vid2aud.ico,0'" in script
    assert script.rstrip().endswith("$link.Save()")


def test_encoded_command_round_trip():
    script = "$x = 'C:\\Users\\Andrés'\n"
    assert base64.b64decode(encoded_command(script)).decode("utf-16-le") == script

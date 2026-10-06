"""Instala el lanzador de escritorio de vid2aud.

En Linux escribe el icono del sello en PNG y el ``.desktop`` en la carpeta de
datos del usuario; en Windows, el icono en ICO y un acceso directo en el menu
Inicio. Recibe el icono ya dibujado: este gestor no importa la UI.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QPixmap

from logic._00_logic_launcher import (
    LauncherPaths,
    desktop_entry,
    encoded_command,
    launcher_paths,
    shortcut_script,
    windows_launcher_paths,
)
from paths import ROOT

logger = logging.getLogger(__name__)

# En Windows, que PowerShell no abra una consola; en Linux vale 0.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_POWERSHELL_TIMEOUT_S = 60


def default_data_home() -> Path:
    """``$XDG_DATA_HOME`` o, si no esta definido, ``~/.local/share``."""
    value = os.environ.get("XDG_DATA_HOME", "")
    return Path(value) if value else Path.home() / ".local" / "share"


def install_launcher(icon: QPixmap, data_home: Path | None = None) -> LauncherPaths:
    """Instala el lanzador del sistema actual; lo reemplaza si ya existe."""
    if sys.platform == "win32":
        return _install_windows(icon)
    if sys.platform == "darwin":
        raise OSError(
            "El lanzador solo se instala en Linux y Windows; en macOS usa python main.py."
        )
    return _install_freedesktop(icon, data_home or default_data_home())


def _save_icon(icon: QPixmap, target: Path, image_format: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not icon.save(str(target), image_format):
        raise OSError(f"No se pudo guardar el icono en {target}")


def _install_freedesktop(icon: QPixmap, data_home: Path) -> LauncherPaths:
    """Escribe el PNG y el ``.desktop``."""
    paths = launcher_paths(data_home)
    _save_icon(icon, paths.icon_file, "PNG")
    paths.shortcut_file.parent.mkdir(parents=True, exist_ok=True)
    entry = desktop_entry(Path(sys.executable), ROOT / "main.py", paths.icon_file)
    paths.shortcut_file.write_text(entry, encoding="utf-8")
    paths.shortcut_file.chmod(0o755)
    logger.info("Lanzador instalado en %s (icono en %s)", paths.shortcut_file, paths.icon_file)
    return paths


def _windows_dir(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable, "")
    return Path(value) if value else fallback


def _install_windows(icon: QPixmap) -> LauncherPaths:
    """Escribe el ICO y crea el ``.lnk`` del menu Inicio con PowerShell."""
    appdata = _windows_dir("APPDATA", Path.home() / "AppData" / "Roaming")
    local = _windows_dir("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    programs = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    paths = windows_launcher_paths(programs, local)
    _save_icon(icon, paths.icon_file, "ICO")
    paths.shortcut_file.parent.mkdir(parents=True, exist_ok=True)

    # pythonw.exe abre la ventana sin dejar una consola negra detras.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = pythonw if pythonw.is_file() else Path(sys.executable)
    script = shortcut_script(target, ROOT / "main.py", paths)
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded_command(script),
    ]
    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=_POWERSHELL_TIMEOUT_S,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError(f"No se pudo ejecutar PowerShell: {exc}") from exc
    if done.returncode != 0:
        raise OSError(f"PowerShell no pudo crear el acceso directo: {done.stderr.strip()[-400:]}")
    logger.info("Acceso directo creado en %s (icono en %s)", paths.shortcut_file, paths.icon_file)
    return paths

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig, load_app_config, save_app_config
from logic._00_logic_main import MainLogic
from ui.blocks.icons import GlyphButton, set_icon_font
from ui.blocks.logo import app_icon, seal_pixmap
from ui.theme import (
    Kind,
    ThemeFonts,
    apply_theme,
    next_theme,
    resolve_theme,
    set_kind,
    sidebar_palette,
    system_is_dark,
)

logger = logging.getLogger(__name__)

WINDOW_TITLE = "vid2aud"
APP_NAME = "vid2aud"
WINDOW_SIZE = (660, 400)
MIN_SIZE = (600, 380)
SIDEBAR_WIDTH = 52
LOGO_SIZE = 34
NAV_ICON_SIZE = 22
THEME_GLYPHS = {"system": "circle-half", "light": "sun", "dark": "moon"}
THEME_TIPS = {
    "system": "Tema: como el escritorio",
    "light": "Tema: claro",
    "dark": "Tema: oscuro",
}


class MainWindow(QWidget):
    """
    Ventana principal: barra lateral oscura (sello, modulos, tema) y area de trabajo.

    Es la RAIZ DE COMPOSICION de la aplicacion: carga letras, iconos y tema, y
    construye cada modulo inyectandole su coordinador. Ninguna UI de modulo crea
    gestores ni servicios.
    """

    def __init__(
        self,
        config: AppConfig,
        is_admin: bool = False,
        save_config: Callable[[AppConfig], bool] = save_app_config,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._save_config = save_config  # capturas y pruebas pasan uno que no escribe
        self.logic = MainLogic(is_admin=is_admin)
        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, GlyphButton] = {}
        self._fonts = self._load_assets()
        self._apply_theme()

        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(app_icon())
        self._build_ui()
        self._build_navigation()
        self._configure_geometry()

        default_id = self.logic.get_default_module_id()
        if default_id:
            self._load_module(default_id)

    # -- Tema e identidad --------------------------------------

    @staticmethod
    def _load_assets() -> ThemeFonts:
        # Imports diferidos: los gestores leen archivos y la UI no.
        from managers.app_fonts import load_app_fonts
        from managers.icon_font import load_icon_font

        set_icon_font(*load_icon_font())
        return ThemeFonts(*load_app_fonts())

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        colors = resolve_theme(self._config.theme, system_is_dark(app))
        apply_theme(app, self._fonts, colors)

    def _cycle_theme(self) -> None:
        self._config.theme = next_theme(self._config.theme)
        self._save_config(self._config)
        self._apply_theme()
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        self.sidebar.setPalette(sidebar_palette(self.palette()))
        self.logo.setPixmap(seal_pixmap(LOGO_SIZE, on_dark=True))
        self.theme_button.set_glyph(THEME_GLYPHS[self._config.theme])
        self.theme_button.setToolTip(THEME_TIPS[self._config.theme])

    # -- Construccion de la interfaz ---------------------------

    def _configure_geometry(self) -> None:
        self.setMinimumSize(*MIN_SIZE)
        self.resize(*WINDOW_SIZE)
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            frame = self.frameGeometry()
            frame.moveCenter(area.center())
            self.move(frame.topLeft())

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QFrame()
        set_kind(self.sidebar, Kind.SIDEBAR)
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(6, 12, 6, 10)
        self.sidebar_layout.setSpacing(8)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.logo.setToolTip(APP_NAME)
        self.sidebar_layout.addWidget(self.logo)
        self.sidebar_layout.addSpacing(6)
        self.sidebar_layout.addStretch(1)
        self.theme_button = GlyphButton("circle-half", "", NAV_ICON_SIZE - 4)
        self.theme_button.clicked.connect(self._cycle_theme)
        self.sidebar_layout.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.workspace_stack = QStackedWidget()
        root.addWidget(self.sidebar)
        root.addWidget(self.workspace_stack, 1)
        self._refresh_sidebar()

    def _build_navigation(self) -> None:
        group = QButtonGroup(self)
        group.setExclusive(True)
        items = self.logic.get_navigation_items()
        if len(items) < 2:
            return  # con un solo modulo la barra solo lleva el sello y el tema
        for item in items:
            button = GlyphButton(item.icon or "square", item.label, NAV_ICON_SIZE)
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, mid=item.module_id: self._load_module(mid))
            group.addButton(button)
            self._nav_buttons[item.module_id] = button
            index = self.sidebar_layout.count() - 2  # antes del espacio y del boton de tema
            self.sidebar_layout.insertWidget(index, button, 0, Qt.AlignmentFlag.AlignHCenter)

    # -- Navegacion --------------------------------------------

    def _load_module(self, module_id: str) -> None:
        payload = self.logic.open_module(module_id)
        if not payload["ok"]:
            logger.warning("Modulo desconocido: %s", module_id)
            return
        if module_id in self._nav_buttons:
            self._nav_buttons[module_id].setChecked(True)
        page = self._pages.get(module_id)
        if page is None:
            page = self._create_module_widget(module_id)
            self._pages[module_id] = page
            self.workspace_stack.addWidget(page)
        self.workspace_stack.setCurrentWidget(page)

    def _create_module_widget(self, module_id: str) -> QWidget:
        # Los imports van dentro de cada rama: un modulo se carga solo al abrirlo.
        # new_module.py agrega ramas antes del marcador.

        if module_id == "convert":
            from modules.mod_02_convert._02_coordinator import ConvertCoordinator
            from modules.mod_02_convert.ui._02_ui_convert import ConvertWidget

            coordinator = ConvertCoordinator(self._config, self._save_config)
            return ConvertWidget(coordinator=coordinator)

        # [python-programmer:module-factory]

        placeholder = QLabel(f"Módulo '{module_id}' - próximamente.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return placeholder

    # -- Cierre ------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (nombre impuesto por Qt)
        # Cada pagina de modulo libera sus hilos en su propio closeEvent.
        for page in self._pages.values():
            page.close()
        super().closeEvent(event)


# -- Punto de entrada ------------------------------------------


def run_app() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_NAME)
    window = MainWindow(config=load_app_config())
    window.show()
    sys.exit(app.exec())

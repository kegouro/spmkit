"""Workspace — la ventana principal del rediseño.

Reemplaza el modelo de 7 pestañas planas por: una **barra de perspectivas** (arriba),
un **lienzo central** (que cambia según la perspectiva), **paneles acoplables** (docks)
alrededor, una **paleta de comandos** (⌘K) y una **barra de estado** con progreso
cancelable global. El tema (grafito/teal) se aplica a la ``QApplication``.

Los paneles se inyectan (por defecto, placeholders); las perspectivas deciden cuál va
al centro y qué docks se muestran.
"""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.design import theme
from spmkit.gui.panels.base import Panel
from spmkit.gui.shell.command_palette import Command, CommandPalette
from spmkit.gui.shell.perspectives import (
    ALL_PANELS,
    PANEL_LABELS,
    PERSPECTIVES,
    perspective,
)
from spmkit.gui.shell.status_bar import ProgressStatusBar

#: Paneles que ocupan el lienzo central (uno por perspectiva).
CENTRAL_PANELS = frozenset(
    {"image_canvas", "force_canvas", "map_canvas", "batch_table", "figure_editor", "simulator"}
)

#: Paneles-dock y su área por defecto.
_DOCK_AREAS = {
    "navigator": Qt.DockWidgetArea.LeftDockWidgetArea,
    "inspector": Qt.DockWidgetArea.RightDockWidgetArea,
    "histogram": Qt.DockWidgetArea.RightDockWidgetArea,
    "pipeline": Qt.DockWidgetArea.BottomDockWidgetArea,
    "log": Qt.DockWidgetArea.BottomDockWidgetArea,
}


class PlaceholderPanel(Panel):
    """Panel de relleno para la Fase B (los paneles reales llegan por fase)."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        self.title = label
        super().__init__(parent)

    def build(self) -> QWidget:
        content = QWidget()
        lay = QVBoxLayout(content)
        heading = QLabel(self.title)
        heading.setProperty("role", "title")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("panel en construcción")
        hint.setProperty("role", "muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        lay.addWidget(heading)
        lay.addWidget(hint)
        lay.addStretch(1)
        return content


def default_panels() -> dict[str, Panel]:
    """Construye un panel placeholder por cada clave conocida."""
    return {key: PlaceholderPanel(PANEL_LABELS.get(key, key)) for key in ALL_PANELS}


class Workspace(QMainWindow):
    """Ventana principal: perspectivas + lienzo central + docks + paleta + estado."""

    def __init__(
        self,
        panels: dict[str, Panel] | None = None,
        mode: str = "dark",
        extra_commands: list[Command] | None = None,
        persist: bool = False,
    ) -> None:
        super().__init__()
        self.setWindowTitle("spmkit")
        self.resize(1200, 760)
        # Persistencia opt-in (los tests construyen sin persistir para no contaminar QSettings).
        self._settings: QSettings | None = QSettings("spmkit", "spmkit") if persist else None
        self._mode = self._saved("theme", mode)
        # Placeholders por defecto, sobrescritos por los paneles reales inyectados.
        merged = default_panels()
        if panels:
            merged.update(panels)
        self._panels = merged
        self._extra_commands = list(extra_commands or ())
        self._docks: dict[str, QDockWidget] = {}
        self._active = ""

        self._status = ProgressStatusBar(self)
        self.setStatusBar(self._status)

        self._central = QStackedWidget()
        self.setCentralWidget(self._central)
        self._central_index: dict[str, int] = {}

        self._build_perspective_bar()
        self._build_panels()
        self._commands = self._default_commands()
        self._install_shortcuts()

        app = QApplication.instance()
        if app is not None:
            theme.apply(app, self._mode)

        self._restore_geometry()
        self.set_perspective(self._saved("perspective", "force"))

    # ---- persistencia (opt-in) ----
    def _saved(self, key: str, default: str) -> str:
        if self._settings is None:
            return default
        value = self._settings.value(key, default)
        return str(value) if value is not None else default

    def _restore_geometry(self) -> None:
        if self._settings is None:
            return
        geo = self._settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def _persist(self, key: str, value: object) -> None:
        if self._settings is not None:
            self._settings.setValue(key, value)

    def closeEvent(self, event: object) -> None:  # noqa: N802 - override Qt
        if self._settings is not None:
            self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)  # type: ignore[arg-type]

    # ---- construcción ----
    def _build_perspective_bar(self) -> None:
        bar = QToolBar("Perspectivas")
        bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self._persp_actions: dict[str, QAction] = {}
        for persp in PERSPECTIVES:
            action = QAction(persp.label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, k=persp.key: self.set_perspective(k))
            bar.addAction(action)
            self._persp_actions[persp.key] = action

    def _build_panels(self) -> None:
        for key in ALL_PANELS:
            panel = self._panels.get(key)
            if panel is None:
                continue
            if key in CENTRAL_PANELS:
                self._central_index[key] = self._central.addWidget(panel)
            else:
                dock = QDockWidget(PANEL_LABELS.get(key, key), self)
                dock.setObjectName(f"dock_{key}")
                dock.setWidget(panel)
                self.addDockWidget(
                    _DOCK_AREAS.get(key, Qt.DockWidgetArea.RightDockWidgetArea), dock
                )
                dock.hide()
                self._docks[key] = dock

    def _install_shortcuts(self) -> None:
        palette = QAction("Paleta de comandos", self)
        palette.setShortcut(QKeySequence("Ctrl+K"))
        palette.triggered.connect(self.open_command_palette)
        self.addAction(palette)

        toggle = QAction("Alternar tema", self)
        toggle.setShortcut(QKeySequence("Ctrl+Shift+L"))
        toggle.triggered.connect(self.toggle_theme)
        self.addAction(toggle)

    def _default_commands(self) -> list[Command]:
        commands = [
            Command(f"Ir a {p.label}", partial(self.set_perspective, p.key)) for p in PERSPECTIVES
        ]
        commands.append(Command("Tema: alternar claro/oscuro", self.toggle_theme, "Ctrl+Shift+L"))
        commands.extend(self._extra_commands)
        return commands

    # ---- API ----
    def register_command(self, command: Command, install_shortcut: bool = True) -> None:
        """Añade un comando a la paleta y, si tiene atajo, lo instala como QAction."""
        self._commands.append(command)
        if install_shortcut and command.shortcut:
            action = QAction(command.title, self)
            action.setShortcut(QKeySequence(command.shortcut))
            action.triggered.connect(lambda _checked=False: command.callback())
            self.addAction(action)

    def set_perspective(self, key: str) -> None:
        """Activa una perspectiva: cambia el lienzo central y muestra sus docks."""
        persp = perspective(key)
        central_key = next((k for k in persp.panels if k in CENTRAL_PANELS), None)
        if central_key is not None and central_key in self._central_index:
            self._central.setCurrentIndex(self._central_index[central_key])
        for panel_key, dock in self._docks.items():
            dock.setVisible(panel_key in persp.panels)
        for panel_key, action in self._persp_actions.items():
            action.setChecked(panel_key == key)
        self._active = key
        self._persist("perspective", key)

    @property
    def active_perspective(self) -> str:
        return self._active

    def panel(self, key: str) -> Panel | None:
        """Devuelve el panel montado bajo ``key`` (para tests, plugins y estado)."""
        return self._panels.get(key)

    def show_status(self, message: str) -> None:
        """Muestra un mensaje en la barra de estado."""
        self._status.set_message(message)

    def bind_task(self, task: object) -> None:
        """Engancha un ``Task`` a la barra de progreso global (progreso + cancelar)."""
        self._status.bind_task(task)

    def visible_docks(self) -> set[str]:
        """Claves de los docks mostrados en la perspectiva activa (para tests/estado)."""
        return {key for key, dock in self._docks.items() if not dock.isHidden()}

    def open_command_palette(self) -> None:
        CommandPalette(self._commands, self).show()

    def toggle_theme(self) -> None:
        self._mode = "light" if self._mode == "dark" else "dark"
        app = QApplication.instance()
        if app is not None:
            theme.apply(app, self._mode)
        self._persist("theme", self._mode)

    @property
    def mode(self) -> str:
        return self._mode

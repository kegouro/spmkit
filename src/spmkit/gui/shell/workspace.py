"""Workspace — la ventana principal del rediseño.

Reemplaza el modelo de 7 pestañas planas por: una **barra de perspectivas** (arriba),
un **lienzo central** (que cambia según la perspectiva), **paneles acoplables** (docks)
alrededor, una **paleta de comandos** (⌘K) y una **barra de estado** con progreso
cancelable global. La **apariencia** (tema/acento/fuente, con presets) se aplica a la
``QApplication`` y se persiste (ver ``design/appearance.py`` y el diálogo de apariencia).

Los paneles se inyectan (por defecto, placeholders); las perspectivas deciden cuál va
al centro y qué docks se muestran.
"""

from __future__ import annotations

from functools import partial

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
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

from spmkit.gui.design.appearance import (
    Appearance,
    apply_appearance,
    load_appearance,
    save_appearance,
)
from spmkit.gui.extensions import PerspectiveSpec
from spmkit.gui.panels.base import Panel
from spmkit.gui.shell.command_palette import Command, CommandPalette
from spmkit.gui.shell.perspectives import (
    CENTRAL_PANELS,
    DOCK_AREAS,
    PANEL_LABELS,
    PERSPECTIVES,
)
from spmkit.gui.shell.status_bar import ProgressStatusBar

#: Traducción de las áreas de dock (string, agnósticas de toolkit) a las de Qt.
_AREA_MAP = {
    "left": Qt.DockWidgetArea.LeftDockWidgetArea,
    "right": Qt.DockWidgetArea.RightDockWidgetArea,
    "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
    "top": Qt.DockWidgetArea.TopDockWidgetArea,
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


def default_panels(labels: dict[str, str]) -> dict[str, Panel]:
    """Construye un panel placeholder por cada clave conocida."""
    return {key: PlaceholderPanel(label) for key, label in labels.items()}


class Workspace(QMainWindow):
    """Ventana principal: perspectivas + lienzo central + docks + paleta + estado."""

    #: Se emite con la ruta de un archivo soltado sobre la ventana (drag & drop).
    fileDropped = pyqtSignal(str)

    def __init__(
        self,
        panels: dict[str, Panel] | None = None,
        mode: str = "dark",
        extra_commands: list[Command] | None = None,
        persist: bool = False,
        perspectives: tuple[PerspectiveSpec, ...] = PERSPECTIVES,
        panel_labels: dict[str, str] | None = None,
        dock_areas: dict[str, str] | None = None,
        central_panels: frozenset[str] = CENTRAL_PANELS,
    ) -> None:
        super().__init__()
        self.setWindowTitle("spmkit")
        self.resize(1200, 760)
        self.setAcceptDrops(True)  # abrir archivos arrastrándolos a la ventana
        # Layout de la app: por defecto los módulos de fábrica; ``build_workspace`` inyecta
        # el conjunto completo (fábrica + descubiertos por entry-point).
        self._perspectives = tuple(perspectives)
        self._perspective_by_key = {p.key: p for p in self._perspectives}
        self._panel_labels = dict(panel_labels if panel_labels is not None else PANEL_LABELS)
        self._dock_areas = dict(dock_areas if dock_areas is not None else DOCK_AREAS)
        self._central_keys = frozenset(central_panels)
        # Persistencia opt-in (los tests construyen sin persistir para no contaminar QSettings).
        self._settings: QSettings | None = QSettings("spmkit", "spmkit") if persist else None
        self._appearance = (
            load_appearance(self._settings)
            if self._settings is not None
            else Appearance(theme=mode)
        )
        # Placeholders por defecto, sobrescritos por los paneles reales inyectados.
        merged = default_panels(self._panel_labels)
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
            apply_appearance(app, self._appearance)

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

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802 - override Qt
        if self._settings is not None:
            self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # ---- drag & drop de archivos ----
    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:  # noqa: N802 - override Qt
        if event is not None and (md := event.mimeData()) is not None and md.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802 - override Qt
        if event is None or (md := event.mimeData()) is None:
            return
        for url in md.urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return

    # ---- construcción ----
    def _build_perspective_bar(self) -> None:
        bar = QToolBar("Barra principal")
        bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self._persp_bar = bar
        self._first_persp_action: QAction | None = None
        self._persp_actions: dict[str, QAction] = {}
        for persp in self._perspectives:
            action = QAction(persp.label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, k=persp.key: self.set_perspective(k))
            bar.addAction(action)
            if self._first_persp_action is None:
                self._first_persp_action = action
            self._persp_actions[persp.key] = action

    def add_toolbar_action(
        self, text: str, callback: object, shortcut: str | None = None
    ) -> QAction:
        """Añade un botón visible a la izquierda de la barra (antes de las perspectivas).

        Para acciones frecuentes (abrir/guardar): más descubrible que sólo la paleta ⌘K.
        """
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False: callback())  # type: ignore[operator]
        if self._first_persp_action is not None:
            self._persp_bar.insertAction(self._first_persp_action, action)
        else:
            self._persp_bar.addAction(action)
        return action

    def add_toolbar_separator(self) -> None:
        """Separador visual entre los botones de archivo y las perspectivas."""
        if self._first_persp_action is not None:
            self._persp_bar.insertSeparator(self._first_persp_action)

    def _build_panels(self) -> None:
        for key, panel in self._panels.items():
            if panel is None:
                continue
            if key in self._central_keys:
                self._central_index[key] = self._central.addWidget(panel)
            else:
                dock = QDockWidget(self._panel_labels.get(key, key), self)
                dock.setObjectName(f"dock_{key}")
                dock.setWidget(panel)
                area = _AREA_MAP.get(self._dock_areas.get(key, "right"), _AREA_MAP["right"])
                self.addDockWidget(area, dock)
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
            Command(f"Ir a {p.label}", partial(self.set_perspective, p.key))
            for p in self._perspectives
        ]
        commands.append(Command("Tema: alternar claro/oscuro", self.toggle_theme, "Ctrl+Shift+L"))
        commands.append(Command("Personalizar apariencia…", self.open_appearance, "Ctrl+Shift+A"))
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
        persp = self._perspective_by_key.get(key)
        if persp is None:  # clave desconocida (p. ej. una perspectiva persistida ya retirada)
            return
        central_key = next((k for k in persp.panels if k in self._central_keys), None)
        if central_key is not None and central_key in self._central_index:
            self._central.setCurrentIndex(self._central_index[central_key])
            # Re-render al mostrar (como main_window.currentChanged→refresh): corrige el
            # lienzo en blanco de paneles que sólo pintan al hacerse visibles (simulador).
            central = self._panels.get(central_key)
            if central is not None:
                central.refresh_safe()
        for panel_key, dock in self._docks.items():
            visible = panel_key in persp.panels
            dock.setVisible(visible)
            if visible:  # re-sincroniza el dock con el estado actual del VM (evita "olvidar"
                panel = self._panels.get(panel_key)  # datos ya cargados al cambiar de perspectiva)
                if panel is not None:
                    panel.refresh_safe()
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
        """Alterna claro/oscuro rápido (Grafito ↔ Papel), preservando acento/fuente."""
        from dataclasses import replace

        next_theme = "light" if self._appearance.theme == "dark" else "dark"
        self.set_appearance(replace(self._appearance, theme=next_theme))

    def set_appearance(self, appearance: Appearance) -> None:
        """Aplica y persiste una apariencia (tema + acento + fuente)."""
        self._appearance = appearance.normalized()
        app = QApplication.instance()
        if app is not None:
            apply_appearance(app, self._appearance)
        if self._settings is not None:
            save_appearance(self._settings, self._appearance)

    def open_appearance(self) -> None:
        """Abre el diálogo de apariencia con vista previa en vivo (revierte al cancelar)."""
        from spmkit.gui.widgets import AppearanceDialog

        original = self._appearance
        dialog = AppearanceDialog(original, self)
        dialog.changed.connect(self._preview_appearance)  # vista previa en vivo
        if dialog.exec():
            self.set_appearance(dialog.appearance())
        else:
            self.set_appearance(original)  # cancelado → revierte

    def _preview_appearance(self, appearance: Appearance) -> None:
        """Aplica (sin persistir) para la vista previa mientras el diálogo está abierto."""
        app = QApplication.instance()
        if app is not None:
            apply_appearance(app, appearance.normalized())

    @property
    def appearance(self) -> Appearance:
        return self._appearance

    @property
    def mode(self) -> str:
        return self._appearance.theme

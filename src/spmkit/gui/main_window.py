"""Ventana principal: shell por pestañas + tema + interop Gwyddion.

La capa GUI solo presenta y orquesta; toda carga/análisis pasa por
``spmkit.core``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from spmkit import load
from spmkit.core.io import save_gwy, supported_extensions
from spmkit.core.models import SPMData
from spmkit.gui import theme
from spmkit.gui.compare_tab import CompareTab
from spmkit.gui.figure_tab import FigureTab
from spmkit.gui.nanomech_tab import NanomechTab
from spmkit.gui.viewer_tab import ViewerTab
from spmkit.gui.welcome import WelcomeDialog

_MAX_RECENT = 8


class MainWindow(QtWidgets.QMainWindow):
    """Ventana principal de spmkit."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("spmkit · Analizador AFM/KPFM")
        self.resize(1280, 820)
        self.setAcceptDrops(True)

        self._data: SPMData | None = None
        self._settings = QtCore.QSettings("SPMLabUTFSM", "spmkit")
        self._theme = self._settings.value("theme", "dark", type=str)

        self.viewer = ViewerTab()
        self.nanomech = NanomechTab()
        self.figure = FigureTab()
        self.compare = CompareTab()
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.viewer, "Visor")
        self.tabs.addTab(self.nanomech, "Nanomecánica")
        self.tabs.addTab(self.figure, "Editor de figuras")
        self.tabs.addTab(self.compare, "Comparar")

        container = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(container)
        outer.setContentsMargins(14, 8, 14, 12)
        outer.setSpacing(8)
        outer.addWidget(self.tabs)
        self.setCentralWidget(container)

        self._build_toolbar()
        self._setup_shortcuts()
        self.statusBar().showMessage("Abre un archivo .nid / .nhf / .gwy o arrástralo aquí.")

    def _setup_shortcuts(self) -> None:
        """Atajos de teclado (quality of life)."""
        sc = QtGui.QShortcut
        sc(QtGui.QKeySequence.StandardKey.Open, self, self._open_dialog)
        sc(QtGui.QKeySequence("Ctrl+R"), self, self._make_report)
        sc(QtGui.QKeySequence("Ctrl+D"), self, self._toggle_theme)
        for i in range(4):
            sc(QtGui.QKeySequence(f"Ctrl+{i + 1}"), self, lambda i=i: self.tabs.setCurrentIndex(i))

    def show_welcome(self) -> None:
        """Muestra el diálogo de bienvenida (solo en el primer arranque)."""
        WelcomeDialog.maybe_show(self, self._settings)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Principal")
        tb.setMovable(False)

        wordmark = QtWidgets.QLabel("  spmkit")
        wordmark.setProperty("role", "wordmark")
        tb.addWidget(wordmark)
        tag = QtWidgets.QLabel("AFM · KPFM   ")
        tag.setProperty("role", "muted")
        tb.addWidget(tag)
        tb.addSeparator()

        tb.addAction("Abrir", self._open_dialog)

        self.recent_btn = QtWidgets.QToolButton()
        self.recent_btn.setText("Recientes ▾")
        self.recent_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.recent_menu = QtWidgets.QMenu()
        self.recent_btn.setMenu(self.recent_menu)
        tb.addWidget(self.recent_btn)
        self._refresh_recent()

        tb.addSeparator()
        tb.addAction("Reporte…", self._make_report)
        tb.addAction("Exportar .gwy", self._export_gwy)
        tb.addAction("Abrir en Gwyddion", self._open_in_gwyddion)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        tb.addWidget(spacer)
        self.theme_action = tb.addAction("☀ / 🌙", self._toggle_theme)

    # ------------------------------------------------------------- carga
    def _open_dialog(self) -> None:
        exts = " ".join(f"*{e}" for e in supported_extensions())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Abrir archivo SPM", "", f"Archivos SPM ({exts})"
        )
        if path:
            self._load_path(path)

    def _load_path(self, path: str) -> None:
        try:
            self._data = load(path)
        except Exception as exc:  # noqa: BLE001 - mostrar al usuario
            QtWidgets.QMessageBox.critical(self, "Error al abrir", str(exc))
            return
        for tab in (self.viewer, self.nanomech, self.figure):
            tab.set_data(self._data)
        self.setWindowTitle(f"spmkit · {Path(path).name}")
        self.statusBar().showMessage(f"{Path(path).name} · {len(self._data)} canales")
        self._add_recent(path)

    # ---------------------------------------------------------- recientes
    def _recent_list(self) -> list[str]:
        return list(self._settings.value("recent", [], type=list))

    def _add_recent(self, path: str) -> None:
        recent = [p for p in self._recent_list() if p != path]
        recent.insert(0, path)
        self._settings.setValue("recent", recent[:_MAX_RECENT])
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        self.recent_menu.clear()
        recent = self._recent_list()
        if not recent:
            self.recent_menu.addAction("(sin archivos recientes)").setEnabled(False)
            return
        for path in recent:
            self.recent_menu.addAction(Path(path).name, lambda p=path: self._load_path(p))

    # -------------------------------------------------------------- gwy
    def _make_report(self) -> None:
        if self._data is None:
            QtWidgets.QMessageBox.information(self, "Reporte", "Abre un archivo primero.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Guardar reporte", "reporte.html", "HTML (*.html)"
        )
        if not path:
            return
        try:
            from spmkit.core.report import full_report

            channel = "Z-Axis" if "Z-Axis" in self._data.names else self._data.names[0]
            full_report(self._data, path, channel=channel)
        except Exception as exc:  # noqa: BLE001 - mostrar al usuario
            QtWidgets.QMessageBox.critical(self, "Error en reporte", str(exc))
            return
        self.statusBar().showMessage(f"Reporte guardado: {path}")

    def _export_gwy(self) -> None:
        if self._data is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar a Gwyddion", "datos.gwy")
        if path:
            save_gwy(self._data, path)
            self.statusBar().showMessage(f"Exportado a {path}")

    def _open_in_gwyddion(self) -> None:
        if self._data is None or not self._data.source_path:
            QtWidgets.QMessageBox.information(self, "Gwyddion", "Abre un archivo primero.")
            return
        src = self._data.source_path
        gwy = shutil.which("gwyddion")
        try:
            if gwy:
                subprocess.Popen([gwy, src])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Gwyddion", src])
            else:
                raise FileNotFoundError
        except (FileNotFoundError, OSError):
            QtWidgets.QMessageBox.warning(
                self,
                "Gwyddion no encontrado",
                "No se encontró Gwyddion. Instálalo o usa 'Exportar .gwy'.",
            )

    # ------------------------------------------------------------ tema
    def _toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self._settings.setValue("theme", self._theme)  # recordar entre sesiones
        app = QtWidgets.QApplication.instance()
        if app is not None:
            theme.apply_theme(app, self._theme)

    # --------------------------------------------------------- drag&drop
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            self._load_path(urls[0].toLocalFile())

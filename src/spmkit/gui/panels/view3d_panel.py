"""Panel de la vista 3D — superficie de topografía (perspectiva 3D).

Controles (canal, colormap, exageración Z, iluminación) a la izquierda y una superficie
3D matplotlib a la derecha. Reacciona a :class:`View3DViewModel`; toma el canal crudo del
hub de imagen. La exageración es estiramiento **visual** del eje (los datos siguen físicos).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from spmkit.core.models import SPMChannel
from spmkit.core.viz import colormaps
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.view3d_vm import CMAPS, View3DViewModel

#: plot_surface se vuelve lento con mallas grandes; submuestreamos a este máximo por lado.
_MAX_SURFACE_PTS = 200


def _height_units(unit: str, data: np.ndarray) -> tuple[float, str]:
    """Escala/unidad de display para alturas: metros → nm/µm según el relieve."""
    if unit != "m":
        return 1.0, unit
    span = float(np.nanmax(data) - np.nanmin(data)) if data.size else 0.0
    if span < 1e-6:  # relieve sub-µm → nanómetros
        return 1e9, "nm"
    return 1e6, "µm"


class View3DPanel(Panel):
    """Panel central de la perspectiva 3D."""

    title = "Vista 3D"

    def __init__(self, vm: View3DViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.dataChanged.connect(self._on_data)
        vm.changed.connect(self._render)

    def build(self) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)

        side = QWidget()
        side.setMaximumWidth(280)
        form = QFormLayout(side)
        title = QLabel("Vista 3D")
        title.setProperty("role", "title")
        form.addRow(title)

        self._channel = QComboBox()
        self._channel.currentTextChanged.connect(self._vm.set_channel)
        form.addRow("Canal:", self._channel)

        self._cmap = QComboBox()
        self._cmap.addItems(CMAPS)
        self._cmap.currentTextChanged.connect(self._vm.set_cmap)
        form.addRow("Colormap:", self._cmap)

        self._z = QSlider(Qt.Orientation.Horizontal)
        self._z.setRange(1, 2000)
        self._z.setValue(self._vm.z_exag)
        self._z.valueChanged.connect(self._on_z)
        form.addRow("Exageración Z:", self._z)
        self._z_lbl = QLabel(f"×{self._vm.z_exag}")
        form.addRow("", self._z_lbl)

        self._hillshade = QCheckBox("Iluminación (hillshade)")
        self._hillshade.setChecked(self._vm.hillshade)
        self._hillshade.toggled.connect(self._vm.set_hillshade)
        form.addRow(self._hillshade)

        export = QPushButton("Exportar imagen…")
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        form.addRow(export)
        row.addWidget(side)

        self._figure = Figure(figsize=(6, 5))
        self._canvas = FigureCanvasQTAgg(self._figure)
        row.addWidget(self._canvas, 1)
        return root

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        self._render()

    # ---- reacciones ----
    def _on_data(self, names: list) -> None:
        self._channel.blockSignals(True)
        self._channel.clear()
        self._channel.addItems([str(n) for n in names])
        self._channel.setCurrentText(self._vm.channel)
        self._channel.blockSignals(False)

    def _on_z(self, value: int) -> None:
        self._z_lbl.setText(f"×{value}")
        self._vm.set_z_exag(value)

    def _render(self) -> None:
        ch = self._vm.current_channel()
        if ch is None:
            return
        if not ch.is_spatial or min(ch.shape) < 2:
            # Un canal espectral/1D o degenerado no es una superficie: el hillshade
            # (np.gradient) y plot_surface fallarían. Se avisa en vez de romper el panel.
            self._show_message(
                "Este canal no es una superficie 2D de topografía\n"
                "(espectro/línea o demasiado pequeño).\n\n"
                "La Vista 3D necesita una imagen; usa Espectral o Sintonía térmica."
            )
            return
        self._draw(ch, self._vm.z_exag, self._vm.cmap, self._vm.hillshade)

    def _show_message(self, text: str) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color="#94a3b8")
        self._canvas.draw()

    def _draw(self, ch: SPMChannel, z_exag: int, cmap_name: str, hillshade: bool) -> None:
        rows, cols = ch.data.shape
        step_r = max(1, rows // _MAX_SURFACE_PTS)
        step_c = max(1, cols // _MAX_SURFACE_PTS)
        z_data = ch.data[::step_r, ::step_c]
        sub_rows, sub_cols = z_data.shape

        x_um = np.linspace(0.0, ch.x_range * 1e6, sub_cols)
        y_um = np.linspace(0.0, ch.y_range * 1e6, sub_rows)
        mesh_x, mesh_y = np.meshgrid(x_um, y_um)

        z_scale, z_unit = _height_units(ch.unit, z_data)
        surf_z = z_data * z_scale
        cmap = colormaps.get_cmap(cmap_name)

        self._figure.clear()
        ax = self._figure.add_subplot(111, projection="3d")
        if hillshade:
            from matplotlib.colors import LightSource

            ls = LightSource(azdeg=315, altdeg=45)
            z_range = max(np.nanmax(z_data) - np.nanmin(z_data), 1e-30)
            z_norm = (z_data - np.nanmin(z_data)) / z_range
            facecolors = ls.shade(z_norm, cmap=cmap, vert_exag=1.0, blend_mode="overlay")
            ax.plot_surface(
                mesh_x,
                mesh_y,
                surf_z,
                facecolors=facecolors,
                rstride=1,
                cstride=1,
                linewidth=0,
                antialiased=False,
                shade=False,
            )
        else:
            ax.plot_surface(
                mesh_x,
                mesh_y,
                surf_z,
                cmap=cmap,
                rstride=1,
                cstride=1,
                linewidth=0,
                antialiased=False,
            )
        # Exageración = estiramiento visual del eje Z (los valores del eje siguen físicos).
        x_m = ch.x_range or 1.0
        y_m = ch.y_range or x_m
        z_stretch = min(6.0, max(0.02, 0.6 * z_exag / 50.0))
        ax.set_box_aspect((1.0, (y_m / x_m) if x_m else 1.0, z_stretch))
        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")
        ax.set_zlabel(f"Z ({z_unit})")
        ax.set_title(ch.name)
        self._figure.tight_layout()
        self._canvas.draw_idle()

    def _export(self) -> None:
        if self._vm.current_channel() is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar imagen 3D", "vista3d.png", "Imágenes (*.png *.svg *.pdf)"
        )
        if path:
            self._figure.savefig(path, dpi=200, bbox_inches="tight")

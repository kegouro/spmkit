"""Pestaña Vista 3D: superficie 3D de topografía para presentaciones.

Renderiza un canal SPM como superficie 3D interactiva usando matplotlib
(mpl_toolkits.mplot3d) con soporte de iluminación hillshade, exageración Z
y exportación de imagen de alta resolución.
"""

from __future__ import annotations

import numpy as np
from PyQt6 import QtCore, QtWidgets

from spmkit.core.models import SPMData
from spmkit.core.viz import colormaps

# Colormaps disponibles en el selector
_CMAPS = ["gold", "viridis", "inferno", "afmhot", "gray"]

# Submuestreo: máximo de puntos por lado antes de plot_surface.
# plot_surface se vuelve muy lento con mallas >200×200 y ofrece poca ganancia
# visual extra, así que limitamos a este tamaño.
_MAX_SURFACE_PTS = 200


def _height_units(unit: str, data: np.ndarray) -> tuple[float, str]:
    """Escala y unidad de display para alturas: metros → nm/µm según el rango.

    El eje Z se muestra en **unidades físicas legibles** (nm si el rango es sub-µm,
    µm si es mayor), no en metros crudos con notación ``1e-6``.
    """
    if unit != "m":
        return 1.0, unit
    span = float(np.nanmax(data) - np.nanmin(data)) if data.size else 0.0
    if span < 1e-6:  # menos de 1 µm de relieve → nanómetros
        return 1e9, "nm"
    return 1e6, "µm"


class View3DTab(QtWidgets.QWidget):
    """Vista de superficie 3D para topografía AFM/KPFM.

    Muestra el canal seleccionado como una malla 3D coloreada con el colormap
    del laboratorio o cualquier otro de la lista. Soporta:
      - Exageración Z (slider 1–2000, default 50)
      - Iluminación hillshade (LightSource de matplotlib)
      - Submuestreo automático a ≤200×200 para fluidez
      - Exportación PNG a 200 dpi
    """

    def __init__(self) -> None:
        super().__init__()
        self._data: SPMData | None = None
        self._build()

    # ---------------------------------------------------------------- build

    def _build(self) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QtWidgets.QHBoxLayout(self)

        # ---------- panel izquierdo de controles ----------
        side = QtWidgets.QWidget()
        side.setMaximumWidth(280)
        form = QtWidgets.QFormLayout(side)

        title_lbl = QtWidgets.QLabel("Vista 3D")
        title_lbl.setProperty("role", "title")
        form.addRow(title_lbl)

        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.currentTextChanged.connect(self._render)
        form.addRow("Canal:", self.channel_combo)

        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(_CMAPS)
        self.cmap_combo.currentTextChanged.connect(self._render)
        form.addRow("Colormap:", self.cmap_combo)

        # Slider de exageración Z
        self.z_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.z_slider.setRange(1, 2000)
        self.z_slider.setValue(50)
        self.z_slider.valueChanged.connect(self._on_z_changed)
        form.addRow("Exageración Z:", self.z_slider)

        self.z_label = QtWidgets.QLabel("×50")
        form.addRow("", self.z_label)

        self.hillshade_chk = QtWidgets.QCheckBox("Iluminación (hillshade)")
        self.hillshade_chk.setChecked(True)
        self.hillshade_chk.toggled.connect(self._render)
        form.addRow(self.hillshade_chk)

        export_btn = QtWidgets.QPushButton("Exportar imagen…")
        export_btn.setProperty("primary", True)
        export_btn.clicked.connect(self._export)
        form.addRow(export_btn)

        root.addWidget(side)

        # ---------- canvas matplotlib ----------
        self.figure = Figure(figsize=(6, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)
        root.addWidget(self.canvas, stretch=1)

    # ---------------------------------------------------------------- API

    def set_data(self, data: SPMData | None) -> None:
        """Recibe un nuevo SPMData, puebla el combo de canales y renderiza."""
        self._data = data
        # Bloquear señales para no disparar render mientras se reconstruye el combo
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        if data is None:
            self.channel_combo.blockSignals(False)
            self.figure.clear()
            self.canvas.draw_idle()
            return

        self.channel_combo.addItems(data.names)

        # Prefiere canal con "Z-Axis" en el nombre; si no, el primero
        preferred = next((n for n in data.names if "Z-Axis" in n), data.names[0])
        idx = self.channel_combo.findText(preferred)
        if idx >= 0:
            self.channel_combo.setCurrentIndex(idx)

        self.channel_combo.blockSignals(False)
        self._render()

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        if self._data is not None and self.channel_combo.currentText():
            self._render()

    # ---------------------------------------------------------- internos

    def _on_z_changed(self, value: int) -> None:
        """Actualiza la etiqueta y dispara el render."""
        self.z_label.setText(f"×{value}")
        self._render()

    def _render(self) -> None:
        """Reconstruye la superficie 3D con los parámetros actuales."""
        if self._data is None:
            return
        ch_name = self.channel_combo.currentText()
        if not ch_name:
            return

        try:
            ch = self._data[ch_name]
        except KeyError:
            return

        z_exag = self.z_slider.value()
        cmap_name = self.cmap_combo.currentText() or "gold"
        do_hillshade = self.hillshade_chk.isChecked()

        data_raw = ch.data
        rows, cols = data_raw.shape

        # Submuestreo para mantener fluidez con imágenes grandes (≥256×256).
        # Se calcula el paso mínimo necesario para que cada eje no supere
        # _MAX_SURFACE_PTS puntos. Un paso 1 significa sin submuestreo.
        step_r = max(1, rows // _MAX_SURFACE_PTS)
        step_c = max(1, cols // _MAX_SURFACE_PTS)
        z_data = data_raw[::step_r, ::step_c]
        sub_rows, sub_cols = z_data.shape

        # Mallas en µm (extent del canal)
        x_um = np.linspace(0.0, ch.x_range * 1e6, sub_cols)
        y_um = np.linspace(0.0, ch.y_range * 1e6, sub_rows)
        X, Y = np.meshgrid(x_um, y_um)

        # Alturas en unidades físicas legibles (nm/µm) — NO se exageran los datos;
        # la exageración se aplica como estiramiento visual del eje (box aspect).
        z_scale, z_unit = _height_units(ch.unit, z_data)
        Z = z_data * z_scale

        # Colormap
        cmap = colormaps.get_cmap(cmap_name)

        self.figure.clear()
        ax = self.figure.add_subplot(111, projection="3d")

        if do_hillshade:
            from matplotlib.colors import LightSource

            ls = LightSource(azdeg=315, altdeg=45)
            # shade() necesita datos normalizados 0-1 para el array de alturas
            z_range = max(np.nanmax(z_data) - np.nanmin(z_data), 1e-30)
            z_norm = (z_data - np.nanmin(z_data)) / z_range
            facecolors = ls.shade(z_norm, cmap=cmap, vert_exag=1.0, blend_mode="overlay")
            ax.plot_surface(
                X,
                Y,
                Z,
                facecolors=facecolors,
                rstride=1,
                cstride=1,
                linewidth=0,
                antialiased=False,
                shade=False,
            )
        else:
            ax.plot_surface(
                X,
                Y,
                Z,
                cmap=cmap,
                rstride=1,
                cstride=1,
                linewidth=0,
                antialiased=False,
            )

        # Exageración = estiramiento VISUAL del eje Z (los datos siguen físicos, así
        # los valores del eje Z son alturas reales en nm/µm).
        x_m = ch.x_range or 1.0
        y_m = ch.y_range or x_m
        z_stretch = min(6.0, max(0.02, 0.6 * z_exag / 50.0))
        ax.set_box_aspect((1.0, (y_m / x_m) if x_m else 1.0, z_stretch))

        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")
        ax.set_zlabel(f"Z ({z_unit})")
        ax.set_title(ch.name)

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _export(self) -> None:
        """Exporta la figura actual a un archivo de imagen."""
        if self._data is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar imagen 3D",
            "vista3d.png",
            "Imágenes (*.png *.svg *.pdf)",
        )
        if path:
            self.canvas.figure.savefig(path, dpi=200, bbox_inches="tight")

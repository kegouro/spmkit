"""Pestaña Nanomecánica: visor de curvas fuerza-distancia y ajuste de Hertz."""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtWidgets

from spmkit.core.analysis import mechanics
from spmkit.core.models import SPMData


class NanomechTab(QtWidgets.QWidget):
    """Explora curvas de espectroscopía y ajusta el módulo de Young."""

    def __init__(self) -> None:
        super().__init__()
        self._data: SPMData | None = None
        self._curves: list = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QHBoxLayout(self)

        # Panel de controles
        side = QtWidgets.QWidget()
        side.setMaximumWidth(280)
        form = QtWidgets.QFormLayout(side)
        title = QtWidgets.QLabel("Nanomecánica")
        title.setProperty("role", "title")
        form.addRow(title)

        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.currentTextChanged.connect(self._load_curves)
        form.addRow("Canal:", self.channel_combo)

        self.curve_slider = QtWidgets.QSpinBox()
        self.curve_slider.valueChanged.connect(self._plot_curve)
        form.addRow("Curva #:", self.curve_slider)

        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.addItems(["sphere", "paraboloid", "cone"])
        form.addRow("Modelo:", self.model_combo)

        self.radius_spin = QtWidgets.QDoubleSpinBox()
        self.radius_spin.setDecimals(1)
        self.radius_spin.setRange(0.1, 10000)
        self.radius_spin.setValue(10.0)
        self.radius_spin.setSuffix(" nm")
        form.addRow("Radio punta:", self.radius_spin)

        fit_btn = QtWidgets.QPushButton("Ajustar Hertz")
        fit_btn.setProperty("primary", True)
        fit_btn.clicked.connect(self._fit)
        form.addRow(fit_btn)

        map_btn = QtWidgets.QPushButton("Mapa módulo/adhesión")
        map_btn.clicked.connect(self._show_maps)
        form.addRow(map_btn)

        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setProperty("role", "readout")
        self.result_text.setMaximumHeight(160)
        form.addRow(self.result_text)
        root.addWidget(side)

        # Gráfico
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Z", units="m")
        self.plot.setLabel("left", "Fuerza", units="N")
        self.plot.addLegend()
        root.addWidget(self.plot, stretch=1)

    # ---------------------------------------------------------------- API
    def set_data(self, data: SPMData | None) -> None:
        self._data = data
        self.channel_combo.clear()
        if data is None:
            return
        force_channels = sorted({c.name for c in data.channels if c.unit == "N"})
        self.channel_combo.addItems(force_channels)

    # ------------------------------------------------------------ internos
    def _load_curves(self, name: str) -> None:
        if self._data is None or not name:
            return
        try:
            ch = self._data[name]
        except KeyError:
            return
        self._curves = mechanics.extract_curves(ch)
        self.curve_slider.setMaximum(max(0, len(self._curves) - 1))
        self.curve_slider.setValue(len(self._curves) // 2)
        self._plot_curve()

    def _plot_curve(self) -> None:
        if not self._curves:
            return
        i = min(self.curve_slider.value(), len(self._curves) - 1)
        c = self._curves[i]
        self.plot.clear()
        self.plot.plot(c.z, c.force, pen=pg.mkPen("#4ea1ff", width=2), name=f"curva {i}")

    def _fit(self) -> None:
        if not self._curves:
            return
        i = min(self.curve_slider.value(), len(self._curves) - 1)
        try:
            r = mechanics.fit_hertz(
                self._curves[i],
                tip_radius=self.radius_spin.value() * 1e-9,
                model=self.model_combo.currentText(),
            )
        except Exception as exc:  # noqa: BLE001 - mostrar al usuario
            self.result_text.setHtml(f"<span style='color:#ff6b6b'>Error: {exc}</span>")
            return
        self.result_text.setHtml(
            f"<b>Módulo de Young</b><br>{r.young_modulus / 1e6:.4g} MPa<br><br>"
            f"Contacto z0: {r.contact_point * 1e9:.2f} nm<br>"
            f"Adhesión: {r.adhesion * 1e9:.3g} nN<br>"
            f"RMSE: {r.rmse:.3e}"
        )

    def _show_maps(self) -> None:
        if self._data is None or not self.channel_combo.currentText():
            return
        import numpy as np
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        from spmkit.core.viz import colormaps

        ch = self._data[self.channel_combo.currentText()]
        m = mechanics.fit_all(
            ch, tip_radius=self.radius_spin.value() * 1e-9, model=self.model_combo.currentText()
        )
        cmap = colormaps.get_cmap("batlow")
        fig = Figure(figsize=(8, 3.6))
        for i, (arr, title, unit) in enumerate(
            [
                (m.young_modulus / 1e6, "Módulo de Young", "MPa"),
                (m.adhesion * 1e9, "Adhesión", "nN"),
            ]
        ):
            ax = fig.add_subplot(1, 2, i + 1)
            im = ax.imshow(arr, origin="lower", cmap=cmap)
            ax.set_title(f"{title}\nmedia={np.nanmean(arr):.1f} {unit}")
            fig.colorbar(im, ax=ax, fraction=0.046, label=unit)
        fig.suptitle(f"{m.grid_shape[0]}×{m.grid_shape[1]} curvas · {m.n_failed} fallidas")
        fig.tight_layout()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Mapas de propiedades mecánicas")
        dlg.resize(820, 420)
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.addWidget(FigureCanvasQTAgg(fig))
        dlg.exec()

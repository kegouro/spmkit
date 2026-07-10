"""Panel de análisis de imagen — perfil de línea + rugosidad/KPFM + export.

Dock de la perspectiva Imagen: grafica el perfil trazado con el ROI del lienzo y muestra
la estadística de rugosidad (y CPD/KPFM si el canal es de potencial). Exporta el perfil a
CSV con el ``core.export`` puro. Reacciona a :class:`ImageViewModel`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis.profiles import Profile
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ImageViewModel


def _length_scale(magnitude: float) -> tuple[float, str]:
    """Factor y unidad legible para una longitud en metros (nm/µm/mm/m, determinista).

    Reemplaza el auto-prefijo SI de pyqtgraph, que sobre valores grandes mostraba unidades
    absurdas (p. ej. ``km`` en un perfil). El resultado es explícito y verificable.
    """
    m = abs(magnitude)
    if m < 1e-6:
        return 1e9, "nm"
    if m < 1e-3:
        return 1e6, "µm"
    if m < 1.0:
        return 1e3, "mm"
    return 1.0, "m"


def _analysis_html(rough: Any, cpd: Any) -> str:
    if rough is None:
        return "<i>Sin análisis</i>"
    lines = [
        f"<b>Rugosidad ({rough.unit})</b>",
        f"Sa = {rough.Sa:.4g} · Sq = {rough.Sq:.4g} · Sz = {rough.Sz:.4g}",
        f"Ssk = {rough.Ssk:.3g} · Sku = {rough.Sku:.3g}",
    ]
    if cpd is not None:
        lines += [
            "<b>KPFM (CPD)</b>",
            f"media = {cpd.mean:.4g} V · contraste = {cpd.contrast:.4g} V",
        ]
        if cpd.work_function is not None:
            lines.append(f"Φ muestra = {cpd.work_function:.4g} {cpd.work_function_unit}")
    return "<br>".join(lines)


class ImageAnalysisPanel(Panel):
    """Dock: perfil de línea + rugosidad/KPFM + exportar perfil."""

    title = "Análisis"

    def __init__(self, vm: ImageViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.profileChanged.connect(self._on_profile)
        vm.channelChanged.connect(lambda _n: self._refresh_readout())

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel("<i>Sin análisis</i>")
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        wf_row = QHBoxLayout()
        wf_row.addWidget(QLabel("Φ punta (eV):"))
        self._wf = QDoubleSpinBox()
        self._wf.setRange(0.0, 10.0)
        self._wf.setDecimals(3)
        self._wf.setSingleStep(0.1)
        self._wf.setToolTip("Función de trabajo de la punta (eV). 0 = no calcular Φ de la muestra.")
        self._wf.valueChanged.connect(lambda v: self._vm.set_tip_work_function(v or None))
        wf_row.addWidget(self._wf)
        wf_row.addStretch(1)
        lay.addLayout(wf_row)

        lay.addWidget(QLabel("Perfil de línea (arrastra los extremos sobre la imagen)"))
        self._plot = pg.PlotWidget()
        # Unidades deterministas: escalamos nosotros (nm/µm/mm) y desactivamos el auto-prefijo SI
        # de pyqtgraph (que mostraba 'km' sobre valores grandes).
        self._plot.getAxis("bottom").enableAutoSIPrefix(False)
        self._plot.getAxis("left").enableAutoSIPrefix(False)
        self._plot.setLabel("bottom", "Distancia", units="nm")
        self._plot.setLabel("left", "Altura")
        lay.addWidget(self._plot, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        export = QPushButton("Exportar perfil (CSV)…")
        export.clicked.connect(self._export_profile)
        bar.addWidget(export)
        lay.addLayout(bar)
        return root

    # ---- reacciones ----
    def _on_profile(self, prof: Profile | None) -> None:
        import pyqtgraph as pg

        self._plot.clear()
        if prof is None:
            return
        dist = np.asarray(prof.distance, dtype=float)
        height = np.asarray(prof.height, dtype=float)
        dscale, dunit = _length_scale(float(dist.max()) if dist.size else 0.0)
        # Altura: si el canal está en m (topografía) la mostramos en nm; si no, tal cual.
        hscale, hunit = (1e9, "nm") if prof.unit == "m" else (1.0, prof.unit)
        self._plot.plot(dist * dscale, height * hscale, pen=pg.mkPen("#ffb454", width=2))
        self._plot.setLabel("bottom", "Distancia", units=dunit)
        self._plot.setLabel("left", "Altura", units=hunit)

    def _refresh_readout(self) -> None:
        self._readout.setText(_analysis_html(self._vm.roughness(), self._vm.kpfm()))

    def _export_profile(self) -> None:
        from spmkit.core.export import to_csv

        prof = self._vm.last_profile
        if prof is None:
            QMessageBox.information(self, "Sin perfil", "Traza un perfil primero sobre la imagen.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar perfil", "perfil.csv", "CSV (*.csv)")
        if path:
            to_csv(prof, path)

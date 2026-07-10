"""Histograma de la propiedad mapeada — distribución + estadística robusta.

Acompaña al mapa: mientras el mapa muestra la distribución espacial, este panel
resume la población (mediana ± σ, mín/máx, N) e histograma, ignorando las curvas
cuyo ajuste falló (NaN). Se actualiza con el mapa y al cambiar de propiedad.
"""

from __future__ import annotations

import math

import numpy as np
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import PROPERTIES, MapViewModel

_EMPTY = "—"


def _fmt(value: float, unit: str) -> str:
    if not math.isfinite(value):
        return _EMPTY
    return f"{value:.3g} {unit}".rstrip()


class HistogramPanel(Panel):
    """Panel-dock con el histograma y la estadística de la propiedad activa."""

    title = "Histograma"

    def __init__(self, map_vm: MapViewModel, parent: QWidget | None = None) -> None:
        self._vm = map_vm
        super().__init__(parent)
        map_vm.mapReady.connect(lambda _r: self._refresh())
        map_vm.keyChanged.connect(lambda _k: self._refresh())

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setSpacing(6)

        self._stats = QLabel(_EMPTY)
        self._stats.setProperty("role", "readout")
        self._stats.setWordWrap(True)
        lay.addWidget(self._stats)

        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setLabel("left", "cuentas")
        # Los bordes ya vienen escalados a la unidad de PROPERTIES (kPa, nN…) → sin re-prefijo
        # SI de pyqtgraph (evita "MkPa" para módulos de GPa).
        self._plot.getAxis("bottom").enableAutoSIPrefix(False)
        self._bars = self._plot.plot(
            [],
            [],
            stepMode="center",
            fillLevel=0,
            brush=(45, 212, 191, 90),
            pen=pg.mkPen("#2DD4BF"),
        )
        lay.addWidget(self._plot, 1)
        return root

    def _refresh(self) -> None:
        result = self._vm.result
        key = self._vm.key
        label, scale, unit = PROPERTIES.get(key, (key, 1.0, ""))
        self._plot.setLabel("bottom", label, units=unit or None)
        if result is None or key not in result.maps:
            self._bars.setData([], [])
            self._stats.setText(_EMPTY)
            return
        counts, edges = result.histogram(key)
        self._bars.setData(np.asarray(edges) * scale, np.asarray(counts))
        s = result.stats(key)
        rng = f"[{_fmt(s['min'] * scale, unit)}, {_fmt(s['max'] * scale, unit)}]"
        self._stats.setText(
            f"mediana {_fmt(s['median'] * scale, unit)}  ±{_fmt(s['std'] * scale, unit)}"
            f"   ·   N={s['n']}   ·   {rng}"
        )

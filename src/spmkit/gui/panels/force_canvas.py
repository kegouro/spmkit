"""Lienzo de la curva de fuerza — el corazón visual de la perspectiva.

Dibuja la curva activa (approach en gris, retract en ámbar), superpone la línea de
ajuste (teal) y marca el punto de contacto. Un *scrubber* recorre las curvas del
force-volume: al arrastrarlo sólo se re-renderiza (barato), el ajuste va con debounce
en el :class:`ForceViewModel`. Jerarquía de color v2: **dato = neutral, ajuste = teal**
(evita el halation del teal sobre grafito).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from spmkit.core.analysis.forcecurve import display_axis
from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.gui.design import tokens
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel

_NM = 1e9  # m → nm
_NN = 1e9  # N → nN


def _segment_xy(seg: ForceSegment) -> tuple[np.ndarray, np.ndarray, bool]:
    """Devuelve ``(eje_nm, y, calibrado)`` de un segmento para dibujar.

    Si el segmento está calibrado usa fuerza (nN) vs separación/altura (nm); si no,
    la deflexión cruda vs altura (nm). El flag ``calibrado`` decide las etiquetas.
    """
    axis = display_axis(seg.separation, seg.raw_height) * _NM
    if seg.force is not None:
        return axis, np.asarray(seg.force, dtype=np.float64) * _NN, True
    return axis, np.asarray(seg.raw_deflection, dtype=np.float64), False


class ForceCanvasPanel(Panel):
    """Panel central de la perspectiva de curva de fuerza (pyqtgraph)."""

    title = "Curva de fuerza"

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.curveChanged.connect(self._on_curve_changed)
        vm.resultsChanged.connect(self._on_results)

    def build(self) -> QWidget:
        import pyqtgraph as pg  # extra opcional: si falta, el sandbox muestra Error Card

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tokens.SPACE["2"])

        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setLabel("bottom", "Separación", units="nm")
        self._plot.setLabel("left", "Fuerza", units="nN")
        self._plot.addLegend(offset=(-10, 10))

        self._extend_item = self._plot.plot(
            [], [], pen=pg.mkPen(tokens.TRACES["extend"], width=1.6), name="approach"
        )
        self._retract_item = self._plot.plot(
            [], [], pen=pg.mkPen(tokens.TRACES["retract"], width=1.4), name="retract"
        )
        self._fit_item = self._plot.plot(
            [], [], pen=pg.mkPen(tokens.TRACES["fit"], width=2.2), name="ajuste"
        )
        self._contact_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(tokens.TRACES["contact"], width=1.0, style=Qt.PenStyle.DashLine),
        )
        self._contact_line.setVisible(False)
        self._plot.addItem(self._contact_line)

        # Scrubber de curvas + contador.
        controls = QWidget()
        crow = QHBoxLayout(controls)
        crow.setContentsMargins(tokens.SPACE["1"], 0, tokens.SPACE["1"], 0)
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setMinimum(0)
        self._scrubber.valueChanged.connect(self._vm.set_curve)
        self._counter = QLabel("—")
        self._counter.setProperty("role", "readout")
        crow.addWidget(self._scrubber, 1)
        crow.addWidget(self._counter)

        lay.addWidget(self._plot, 1)
        lay.addWidget(controls)

        self._sync_scrubber_range()
        self._on_curve_changed(self._vm.index)
        return root

    # ---- reacciones a la VM ----
    def _on_curve_changed(self, index: int) -> None:
        """Render inmediato de la curva cruda (sin esperar el ajuste)."""
        self._sync_scrubber_range()
        with _blocked(self._scrubber):
            self._scrubber.setValue(index)
        n = self._vm.n_curves
        self._counter.setText(f"{index + 1:>4} / {n}" if n else "—")
        self._fit_item.setData([], [])
        self._contact_line.setVisible(False)
        curve = self._vm.current_curve() if n else None
        if curve is not None:
            self._draw_data(curve)

    def _on_results(self, ctx: dict) -> None:
        """Re-render con la curva calibrada + overlay de ajuste."""
        curve = self._vm.result_curve()
        if curve is not None:
            self._draw_data(curve)
        fit = ctx.get("fit")
        if fit is not None and getattr(fit, "x_fit", None) is not None and len(fit.x_fit):
            self._fit_item.setData(np.asarray(fit.x_fit) * _NM, np.asarray(fit.f_fit) * _NN)
        else:
            self._fit_item.setData([], [])
        cp = ctx.get("contact_point")
        if cp is not None and ctx.get("contact_detected", True):
            self._contact_line.setPos(float(cp) * _NM)
            self._contact_line.setVisible(True)
        else:
            self._contact_line.setVisible(False)

    # ---- dibujo ----
    def _draw_data(self, curve: ForceCurve) -> None:
        calibrated = False
        if curve.extend is not None:
            x, y, calibrated = _segment_xy(curve.extend)
            self._extend_item.setData(x, y)
        else:
            self._extend_item.setData([], [])
        if curve.retract is not None:
            xr, yr, _ = _segment_xy(curve.retract)
            self._retract_item.setData(xr, yr)
        else:
            self._retract_item.setData([], [])
        label, units = ("Fuerza", "nN") if calibrated else ("Deflexión", "")
        self._plot.setLabel("left", label, units=units)

    def _sync_scrubber_range(self) -> None:
        n = self._vm.n_curves
        self._scrubber.setMaximum(max(0, n - 1))
        self._scrubber.setEnabled(n > 1)


class _blocked:
    """Context manager: bloquea señales de un widget mientras se ajusta programático."""

    def __init__(self, widget: QWidget) -> None:
        self._w = widget

    def __enter__(self) -> None:
        self._prev = self._w.blockSignals(True)

    def __exit__(self, *exc: object) -> None:
        self._w.blockSignals(self._prev)

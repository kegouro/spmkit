"""Lienzo de la curva de fuerza — el corazón visual de la perspectiva.

Dibuja la curva activa (approach en gris, retract en ámbar), superpone la línea de
ajuste (teal), marca el contacto y muestra una **tira de residuos** debajo (lo que
ANA/JPK no dan de un vistazo). El eje se conmuta entre **separación** e **indentación
δ** (contacto en el origen). Un *scrubber* recorre las curvas del force-volume: al
arrastrarlo sólo se re-renderiza (barato); el ajuste va con debounce en el
:class:`ForceViewModel`. Jerarquía de color v2: **dato = neutral, ajuste = teal**.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis.forcecurve import display_axis
from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.gui.design import tokens
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel

_NM = 1e9  # m → nm
_NN = 1e9  # N → nN


def _segment_xy(seg: ForceSegment) -> tuple[np.ndarray, np.ndarray, bool]:
    """Devuelve ``(eje_m, y_display, calibrado)`` de un segmento para dibujar.

    Si el segmento está calibrado usa fuerza (nN) vs eje (m); si no, la deflexión
    cruda vs eje. El flag ``calibrado`` decide las etiquetas. El eje se deja en metros
    (el shift de indentación y la escala a nm los aplica el panel).
    """
    axis = display_axis(seg.separation, seg.raw_height)
    if seg.force is not None:
        return axis, np.asarray(seg.force, dtype=np.float64) * _NN, True
    return axis, np.asarray(seg.raw_deflection, dtype=np.float64), False


class _blocked:
    """Context manager: bloquea señales de un widget mientras se ajusta programático."""

    def __init__(self, widget: QWidget) -> None:
        self._w = widget

    def __enter__(self) -> None:
        self._prev = self._w.blockSignals(True)

    def __exit__(self, *exc: object) -> None:
        self._w.blockSignals(self._prev)


class ForceCanvasPanel(Panel):
    """Panel central de la perspectiva de curva de fuerza (pyqtgraph)."""

    title = "Curva de fuerza"

    _PINNED_MAX = 6

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        self._offset = 0.0  # shift del eje (m): contacto en modo indentación
        self._contact: float | None = None
        self._last_ctx: dict = {}
        self._pinned: list = []  # trazas fijadas para comparar
        super().__init__(parent)
        vm.curveChanged.connect(self._on_curve_changed)
        vm.resultsChanged.connect(self._on_results)

    def build(self) -> QWidget:
        import pyqtgraph as pg  # extra opcional: si falta, el sandbox muestra Error Card

        self._pg = pg
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tokens.SPACE["2"])

        glw = pg.GraphicsLayoutWidget()
        self._plot = glw.addPlot(row=0, col=0)
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setLabel("left", "Fuerza", units="nN")
        self._plot.addLegend(offset=(-10, 10))
        self._resid = glw.addPlot(row=1, col=0)
        self._resid.setMaximumHeight(110)
        self._resid.showGrid(x=True, y=True, alpha=0.12)
        self._resid.setLabel("left", "resid", units="nN")
        self._resid.setXLink(self._plot)
        # Los datos ya vienen escalados a nN/nm; sin esto pyqtgraph re-aplica su prefijo SI y
        # muestra unidades absurdas (p. ej. "knN" para fuerzas de µN, "knm" para µm).
        for _ax in (
            self._plot.getAxis("left"),
            self._plot.getAxis("bottom"),
            self._resid.getAxis("left"),
            self._resid.getAxis("bottom"),
        ):
            _ax.enableAutoSIPrefix(False)

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
        self._region = pg.LinearRegionItem(
            brush=(45, 212, 191, 25), pen=pg.mkPen(tokens.TRACES["fit"], width=1.0)
        )
        self._region.setZValue(-5)
        self._region.setVisible(False)
        self._region.sigRegionChangeFinished.connect(self._on_region_changed)
        self._plot.addItem(self._region)
        self._resid.addLine(y=0, pen=pg.mkPen(tokens.TRACES["residual"], width=1.0))
        self._resid_item = self._resid.plot(
            [], [], pen=None, symbol="o", symbolSize=3, symbolBrush=tokens.TRACES["fit"]
        )

        # Controles: modo de eje + scrubber + contador.
        controls = QWidget()
        crow = QHBoxLayout(controls)
        crow.setContentsMargins(tokens.SPACE["1"], 0, tokens.SPACE["1"], 0)
        self._axis_mode = QComboBox()
        self._axis_mode.addItem("Separación", "sep")
        self._axis_mode.addItem("Indentación δ", "ind")
        self._axis_mode.currentIndexChanged.connect(self._on_axis_mode)
        self._region_check = QCheckBox("Región")
        self._region_check.setToolTip("Ajustar sólo dentro de una ventana manual del eje")
        self._region_check.toggled.connect(self._on_region_toggle)
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setMinimum(0)
        self._scrubber.valueChanged.connect(self._vm.set_curve)
        self._counter = QLabel("—")
        self._counter.setProperty("role", "readout")
        self._export_btn = QPushButton("Exportar curva…")
        self._export_btn.setToolTip(
            "CSV científico: ajuste (con unidades) + datos separación/fuerza"
        )
        self._export_btn.clicked.connect(self._export)
        crow.addWidget(self._axis_mode)
        crow.addWidget(self._region_check)
        crow.addWidget(self._scrubber, 1)
        crow.addWidget(self._counter)
        crow.addWidget(self._export_btn)

        lay.addWidget(glw, 1)
        lay.addWidget(controls)

        self._update_axis_label()
        self._sync_scrubber_range()
        self._on_curve_changed(self._vm.index)
        return root

    def _export(self) -> None:
        """Exporta la curva calibrada activa a un CSV científico (ajuste + datos)."""
        from PyQt6.QtWidgets import QFileDialog

        from spmkit.core.export import export_curve

        curve = self._vm.result_curve()
        if curve is None:
            self._counter.setText("aún sin ajuste — espera")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar curva", "curva.csv", "CSV (*.csv)")
        if not path:
            return
        p = self._vm.params
        meta = {
            "modelo": p.get("model", ""),
            "radio_punta_nm": (p.get("tip_radius") or 0.0) * 1e9,
            "poisson": p.get("poisson", ""),
        }
        try:
            export_curve(curve, self._vm.current_results(), path, extra_meta=meta)
            self._counter.setText("curva exportada")
        except Exception as exc:  # noqa: BLE001 - se informa, no tumba
            self._counter.setText(f"export falló: {exc}")

    # ---- reacciones a la VM ----
    def _on_curve_changed(self, index: int) -> None:
        """Render inmediato de la curva cruda (sin esperar el ajuste)."""
        self._sync_scrubber_range()
        with _blocked(self._scrubber):
            self._scrubber.setValue(index)
        n = self._vm.n_curves
        self._counter.setText(f"{index + 1:>4} / {n}" if n else "—")
        self._plot.setTitle(None if n else "Abre una curva de fuerza · ⌘O o arrástrala aquí")
        self._fit_item.setData([], [])
        self._resid_item.setData([], [])
        self._contact_line.setVisible(False)
        self._contact = None
        self._last_ctx = {}
        self._offset = 0.0
        curve = self._vm.current_curve() if n else None
        if curve is not None:
            self._draw_data(curve)

    def _on_results(self, ctx: dict) -> None:
        """Re-render con la curva calibrada + overlay de ajuste + residuos."""
        self._last_ctx = ctx
        cp = ctx.get("contact_point")
        self._contact = float(cp) if isinstance(cp, (int, float)) else None
        self._refresh_offset()
        curve = self._vm.result_curve()
        if curve is not None:
            self._draw_data(curve)
        fit = ctx.get("fit")
        if fit is not None and getattr(fit, "x_fit", None) is not None and len(fit.x_fit):
            self._fit_item.setData(self._x(fit.x_fit), np.asarray(fit.f_fit) * _NN)
            self._resid_item.setData(self._x(fit.x_fit), np.asarray(fit.residual) * _NN)
        else:
            self._fit_item.setData([], [])
            self._resid_item.setData([], [])
        if self._contact is not None and ctx.get("contact_detected", True):
            self._contact_line.setPos(self._x(np.array([self._contact]))[0])
            self._contact_line.setVisible(True)
        else:
            self._contact_line.setVisible(False)

    def _on_axis_mode(self, _idx: int) -> None:
        self._update_axis_label()
        # Re-render con el modo nuevo: si hay ajuste, re-emite todo (datos+fit+residuos);
        # si no, sólo la curva cruda.
        if self._last_ctx:
            self._on_results(self._last_ctx)
        elif self._vm.n_curves:
            self._draw_data(self._vm.current_curve())

    # ---- curvas fijadas (comparación) ----
    def pin_current(self) -> None:
        """Fija la traza approach actual (faded) para comparar con otras curvas."""
        x, y = self._extend_item.getData()
        if x is None or len(x) == 0:
            return
        item = self._plot.plot(x, y, pen=self._pg.mkPen("#5C6875", width=1.0))
        item.setZValue(-10)
        self._pinned.append(item)
        if len(self._pinned) > self._PINNED_MAX:
            self._plot.removeItem(self._pinned.pop(0))

    def clear_pinned(self) -> None:
        """Quita todas las trazas fijadas."""
        for item in self._pinned:
            self._plot.removeItem(item)
        self._pinned.clear()

    # ---- región de ajuste manual (sólo en modo separación) ----
    def _on_region_toggle(self, on: bool) -> None:
        if on:
            with _blocked(self._axis_mode):
                self._axis_mode.setCurrentIndex(self._axis_mode.findData("sep"))
            self._axis_mode.setEnabled(False)
            self._update_axis_label()
            self._init_region_bounds()
            self._region.setVisible(True)
            self._on_region_changed()
        else:
            self._region.setVisible(False)
            self._axis_mode.setEnabled(True)
            self._vm.set_params(fit_min=None, fit_max=None)

    def _init_region_bounds(self) -> None:
        fit = self._last_ctx.get("fit")
        if fit is not None and getattr(fit, "x_fit", None) is not None and len(fit.x_fit):
            xs = self._x(fit.x_fit)  # offset 0 en modo separación
            lo, hi = float(np.min(xs)), float(np.max(xs))
        else:
            lo, hi = self._plot.getViewBox().viewRange()[0]
        with _blocked(self._region):
            self._region.setRegion((lo, hi))

    def _on_region_changed(self, *_args: object) -> None:
        if not self._region.isVisible():
            return
        lo_nm, hi_nm = self._region.getRegion()
        self._vm.set_params(fit_min=lo_nm / _NM, fit_max=hi_nm / _NM)

    # ---- dibujo ----
    def _x(self, axis_m: np.ndarray) -> np.ndarray:
        """Eje en nm, con shift a indentación (contacto en 0) si corresponde."""
        return (np.asarray(axis_m, dtype=np.float64) - self._offset) * _NM

    def _refresh_offset(self) -> None:
        indent = self._axis_mode.currentData() == "ind"
        self._offset = self._contact if (indent and self._contact is not None) else 0.0

    def _draw_data(self, curve: ForceCurve) -> None:
        calibrated = False
        if curve.extend is not None:
            axis, y, calibrated = _segment_xy(curve.extend)
            self._extend_item.setData(self._x(axis), y)
        else:
            self._extend_item.setData([], [])
        if curve.retract is not None:
            axis_r, yr, _ = _segment_xy(curve.retract)
            self._retract_item.setData(self._x(axis_r), yr)
        else:
            self._retract_item.setData([], [])
        label, units = ("Fuerza", "nN") if calibrated else ("Deflexión", "")
        self._plot.setLabel("left", label, units=units)

    def _update_axis_label(self) -> None:
        if self._axis_mode.currentData() == "ind":
            self._resid.setLabel("bottom", "Indentación δ", units="nm")
        else:
            self._resid.setLabel("bottom", "Separación", units="nm")

    def _sync_scrubber_range(self) -> None:
        n = self._vm.n_curves
        self._scrubber.setMaximum(max(0, n - 1))
        self._scrubber.setEnabled(n > 1)

"""Herramientas de vista para espectroscopia. Operan en coordenadas de pantalla y de la traza."""

import math
from functools import partial
from html import escape
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

# ViewBox coordinates stay in nm, nN or V. Only reported quantities are rescaled.
_UNITS = {
    "nm": {"nm": 1.0, "µm": 0.001},
    "nN": {"pN": 1000.0, "nN": 1.0, "µN": 0.001},
    "V": {"mV": 1000.0, "V": 1.0},
}


class AxisLimits(QDialog):
    """Límites en las unidades visibles, con validación antes de modificar el gráfico."""

    def __init__(
        self, plot: Any, x_label: str, y_label: str, scales: tuple[float, float], parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Límites de los ejes")
        form = QFormLayout(self)
        self._fields = []
        self._plot = plot
        self._scales = scales
        for label, bounds, scale in zip((x_label, y_label), plot.viewRange(), scales, strict=True):
            for name, value in zip(("Mínimo", "Máximo"), bounds, strict=True):
                field = QLineEdit(format(value * scale, ".15g"))
                form.addRow(f"{name} · {label}", field)
                self._fields.append(field)
        self._error = QLabel()
        form.addRow(self._error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        try:
            x0, x1, y0, y1 = (
                float(field.text().strip().replace(",", ".")) for field in self._fields
            )
            sx, sy = self._scales
            x0, x1, y0, y1 = x0 / sx, x1 / sx, y0 / sy, y1 / sy
            if not (x0 < x1 and y0 < y1 and math.isfinite(x1 - x0) and math.isfinite(y1 - y0)):
                raise ValueError
        except ValueError:
            self._error.setText("Usa límites finitos con el mínimo menor que el máximo.")
            return
        self._plot.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0)
        super().accept()


class CurveViewTools(QWidget):
    editStyle = pyqtSignal()
    exportView = pyqtSignal()

    def __init__(
        self, plot: Any, residual: Any, graphics: Any, branches: list[tuple[str, Any]]
    ) -> None:
        super().__init__()
        self._plot = plot
        self._view = plot.getViewBox()
        self._residual = residual
        self._branches = branches
        self._reference: tuple[float, float] | None = None
        self._x_label = "Separación (nm)"
        self._y_label = "Fuerza (nN)"
        self._base_unit = "nN"
        self._x_unit = "nm"
        self._y_unit = "nN"
        self._scales = (1.0, 1.0)
        self.aliases: dict[str, str] = {}
        self._x_title, self._y_title = "Separación", "Fuerza"
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        self.mode = QComboBox()
        self.mode.setAccessibleName("Herramienta de la curva")
        self.mode.addItem("Desplazar", "pan")
        self.mode.addItem("Zoom rectangular", "zoom")
        self.mode.addItem("Inspeccionar", "inspect")
        row.addWidget(self.mode)
        self._series = QComboBox()
        self._series.setAccessibleName("Traza que inspeccionar")
        self._series.addItem("Rama más cercana", None)
        for name, _ in branches:
            self._series.addItem(name, name)
        self._series.currentIndexChanged.connect(self._reset_hover)
        row.addWidget(self._series)
        axes = QToolButton()
        axes.setText("Ejes")
        axes.setObjectName("axisTools")
        axes.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(axes)
        menu.addAction("Límites manuales…", self._limits)
        menu.addAction("Ajustar Y al intervalo X visible", self.fit_visible_y)
        self._x_units = menu.addMenu("Unidad X")
        self._y_units = menu.addMenu("Unidad Y")
        menu.aboutToShow.connect(self._unit_menus)
        menu.addSeparator()
        menu.addAction("Estilo de la curva…", self.editStyle.emit)
        menu.addAction("Guardar vista del gráfico…", self.exportView.emit)
        axes.setMenu(menu)
        row.addWidget(axes)
        self.readout = QLabel()
        self.readout.setWordWrap(True)
        self.readout.setProperty("role", "readout")
        self.readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.readout, 1)
        self._clear = QPushButton("Borrar referencia")
        self._clear.clicked.connect(self.clear_probe)
        row.addWidget(self._clear)
        self._marker = pg.ScatterPlotItem(size=10, symbol="o", brush=None, pxMode=True)
        self._anchor = pg.ScatterPlotItem(size=11, symbol="+", pxMode=True)
        for item in (self._marker, self._anchor):
            item.setZValue(20)
            plot.addItem(item, ignoreBounds=True)
        self.mode.currentIndexChanged.connect(self._change_mode)
        self._move_proxy = pg.SignalProxy(
            plot.scene().sigMouseMoved, rateLimit=30, slot=self._mouse_moved
        )
        plot.scene().sigMouseClicked.connect(self._click)
        graphics.viewport().installEventFilter(self)
        self._change_mode()

    def _change_mode(self) -> None:
        mode = self.mode.currentData()
        self._series.setVisible(mode == "inspect")
        self._view.setMouseMode(self._view.RectMode if mode == "zoom" else self._view.PanMode)
        self._view.setCursor(
            Qt.CursorShape.CrossCursor if mode != "pan" else Qt.CursorShape.OpenHandCursor
        )
        self.clear_probe()

    def _reset_hover(self) -> None:
        self._marker.clear()
        self._hint()

    def clear_probe(self) -> None:
        self._reference = None
        self._marker.clear()
        self._anchor.clear()
        self._clear.hide()
        self._hint()

    def _hint(self) -> None:
        hints = {
            "pan": "Arrastra para desplazar · rueda para ampliar",
            "zoom": "Arrastra un rectángulo sobre la curva",
            "inspect": "Acerca el puntero a una rama · clic para fijar la referencia",
        }
        self.readout.setText(hints[self.mode.currentData()])

    def set_units(self, horizontal: str, vertical: str, unit: str) -> None:
        self._x_title, self._y_title = horizontal, vertical
        if unit != self._base_unit:
            self._base_unit = self._y_unit = unit
        self._apply_units()
        self.clear_probe()

    def _unit_menus(self) -> None:
        for axis, menu, units, current in (
            ("x", self._x_units, _UNITS["nm"], self._x_unit),
            ("y", self._y_units, _UNITS[self._base_unit], self._y_unit),
        ):
            menu.clear()
            for unit in units:
                action = menu.addAction(unit)
                action.setCheckable(True)
                action.setChecked(unit == current)
                action.triggered.connect(partial(self._choose_unit, axis, unit))

    def _choose_unit(self, axis: str, unit: str, checked: bool = True) -> None:
        if axis == "x":
            self._x_unit = unit
        else:
            self._y_unit = unit
        self._apply_units()
        self._marker.clear()
        self._hint()

    def _apply_units(self) -> None:
        sx, sy = _UNITS["nm"][self._x_unit], _UNITS[self._base_unit][self._y_unit]
        self._scales = sx, sy
        x_title, y_title = (self.aliases.get(t) or t for t in self.axis_titles())
        self._x_label = f"{x_title} ({self._x_unit})"
        self._y_label = f"{y_title} ({self._y_unit})"
        for plot, side, title, unit, scale in (
            (self._residual, "bottom", x_title, self._x_unit, sx),
            (self._plot, "left", y_title, self._y_unit, sy),
            (
                self._residual,
                "left",
                "Residuo",
                self._y_unit if self._base_unit == "nN" else "nN",
                sy if self._base_unit == "nN" else 1.0,
            ),
        ):
            plot.setLabel(side, escape(title), units=unit)
            plot.getAxis(side).setScale(scale)

    def axis_titles(self) -> tuple[str, str]:
        return self._x_title, self._y_title

    def set_titles(self, names: tuple[str, str]) -> None:
        self.aliases.update(zip(self.axis_titles(), names, strict=True))
        self._apply_units()

    def set_ink(self, color: str) -> None:
        self._marker.setPen(pg.mkPen(color, width=2))
        self._anchor.setPen(pg.mkPen(color, width=2))
        self._anchor.setBrush(color)

    def _limits(self) -> None:
        AxisLimits(self._plot, self._x_label, self._y_label, self._scales, self).exec()

    def fit_visible_y(self) -> None:
        lo, hi = sorted(self._view.viewRange()[0])
        bounds: list[float] = []
        for item in self._plot.listDataItems():
            if not isinstance(item, pg.PlotDataItem) or not item.isVisible() or item.xData is None:
                continue
            x, y = item.xData, item.yData
            selected = y[(x >= lo) & (x <= hi) & np.isfinite(y)]
            if selected.size:
                bounds.extend((float(selected.min()), float(selected.max())))
        if bounds:
            self._view.setYRange(min(bounds), max(bounds), padding=0.05)
        else:
            self.readout.setText("Sin muestras en el intervalo X visible")

    def _nearest(self, scene_pos: QPointF) -> tuple[str, int, float, float] | None:
        if self.mode.currentData() != "inspect" or not self._view.sceneBoundingRect().contains(
            scene_pos
        ):
            return None
        point = self._view.mapSceneToView(scene_pos)
        (xmin, xmax), (ymin, ymax) = self._view.viewRange()
        dx, dy = self._view.viewPixelSize()
        if not dx or not dy:
            return None
        best = None
        radius2 = 18.0**2
        selected = self._series.currentData()
        for name, item in self._branches:
            if (selected is None and name == "Ajuste") or (
                selected is not None and name != selected
            ):
                continue
            x, y = item.xData, item.yData
            if x is None or not len(x) or not item.isVisible():
                continue
            mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
            indices = np.flatnonzero(mask)
            if not len(indices):
                continue
            d2 = ((x[indices] - point.x()) / dx) ** 2 + ((y[indices] - point.y()) / dy) ** 2
            nearest = int(np.argmin(d2))
            if d2[nearest] <= radius2:
                i = int(indices[nearest])
                radius2 = d2[nearest]
                best = name, i, float(x[i]), float(y[i])
        return best

    def _mouse_moved(self, args: tuple[QPointF]) -> None:
        self._move(args[0])

    def _move(self, pos: QPointF) -> None:
        if self.mode.currentData() != "inspect":
            return
        sample = self._nearest(pos)
        if sample is None:
            self._marker.clear()
            self._hint()
            return
        branch, i, x, y = sample
        self._marker.setData([x], [y])
        sx, sy = self._scales
        info = f"{branch} [{i}]   X {x*sx:.6g} {self._x_unit}   Y {y*sy:.6g} {self._y_unit}"
        if self._reference is not None:
            rx, ry = self._reference
            info += f"   ΔX {(x-rx)*sx:.5g} {self._x_unit}   ΔY {(y-ry)*sy:.5g} {self._y_unit}"
        self.readout.setText(info)

    def _click(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and (
            sample := self._nearest(event.scenePos())
        ):
            self._reference = sample[2], sample[3]
            self._anchor.setData([sample[2]], [sample[3]])
            self._clear.show()
            self._move(event.scenePos())

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        if event and event.type() == QEvent.Type.Leave and self.mode.currentData() == "inspect":
            self._marker.clear()
            self._hint()
        return super().eventFilter(obj, event)

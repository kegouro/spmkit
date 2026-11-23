"""Curva de fuerza y residuos con inspección y navegación en coordenadas de visualización."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QIODevice, QRectF, QSaveFile, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QImage, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis.forcecurve import display_axis
from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.gui.design import tokens
from spmkit.gui.design.appearance import Appearance
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel
from spmkit.gui.widgets.curve_style import CurveStyle, CurveStyleDialog

_NM = 1e9  # m → nm
_NN = 1e9  # N → nN


def _segment_xy(seg: ForceSegment) -> tuple[np.ndarray, np.ndarray, str, str]:
    separation = None if seg.separation is None else np.asarray(seg.separation, dtype=np.float64)
    axis = display_axis(separation, seg.raw_height)
    x_name = "Separación" if separation is not None and axis is separation else "Altura"
    if seg.force is not None:
        return axis, np.asarray(seg.force) * _NN, "nN", x_name
    if seg.deflection is not None:
        return axis, np.asarray(seg.deflection) * _NM, "nm", x_name
    return axis, np.asarray(seg.raw_deflection), "V", x_name


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

    openRequested = pyqtSignal()
    adhesionRequested = pyqtSignal()

    _PINNED_MAX = 6

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._style_settings: QSettings | None = None
        self._curve_style = CurveStyle()
        self._appearance = Appearance()
        self._vm = vm
        self._offset = 0.0  # shift del eje (m): contacto en modo indentación
        self._contact: float | None = None
        self._last_ctx: dict = {}
        self._pinned_color = tokens.TRACES["residual"]
        self._pinned: list = []  # trazas fijadas para comparar
        super().__init__(parent)
        vm.volumeChanged.connect(lambda _: self.set_source_name(""))
        vm.curveChanged.connect(self._on_curve_changed)
        vm.resultsChanged.connect(self._on_results)

    def build(self) -> QWidget:
        import pyqtgraph as pg  # extra opcional: si falta, el sandbox muestra Error Card

        from spmkit.gui.widgets.curve_view_tools import CurveViewTools

        self._pg = pg
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tokens.SPACE["2"])

        self._header = QWidget()
        self._header.setObjectName("plotHeader")
        header = QVBoxLayout(self._header)
        header.setContentsMargins(18, 12, 16, 6)
        title = QLabel("Fuerza–distancia")
        title.setProperty("role", "plotTitle")
        self._source = QLabel()
        self._source.setProperty("role", "muted")
        self._source.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(title)
        header.addWidget(self._source)
        lay.addWidget(self._header)

        self._empty = QWidget()
        self._empty.setObjectName("emptyCanvas")
        empty = QVBoxLayout(self._empty)
        empty.addStretch()
        intro = QLabel("Abrir una adquisición")
        intro.setProperty("role", "plotTitle")
        empty.addWidget(intro, alignment=Qt.AlignmentFlag.AlignHCenter)
        hint = QLabel("Arrastra un archivo de AFM o selecciónalo en el disco.")
        hint.setProperty("role", "muted")
        empty.addWidget(hint, alignment=Qt.AlignmentFlag.AlignHCenter)
        button = QPushButton("Seleccionar archivo…")
        button.setProperty("primary", True)
        button.clicked.connect(self.openRequested)
        empty.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch()
        lay.addWidget(self._empty, 1)
        glw = pg.GraphicsLayoutWidget()
        self._graphics = glw
        self._plot = glw.addPlot(row=0, col=0)
        self._plot.showGrid(x=False, y=True, alpha=0.13)
        self._plot.setLabel("left", "Fuerza", units="nN")
        self._plot.getAxis("bottom").setStyle(showValues=False)
        self._legend = self._plot.addLegend(offset=(-10, 10))
        self._resid = glw.addPlot(row=1, col=0)
        self._resid.setMaximumHeight(110)
        self._resid.showGrid(x=False, y=True, alpha=0.09)
        self._resid.setLabel("left", "Residuo", units="nN")
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
            [], [], pen=pg.mkPen(tokens.TRACES["extend"], width=1.6), name="Aproximación"
        )
        self._retract_item = self._plot.plot(
            [], [], pen=pg.mkPen(tokens.TRACES["retract"], width=1.4), name="Retracción"
        )
        self._fit_item = self._plot.plot(
            [], [], pen=pg.mkPen(tokens.TRACES["fit"], width=2.2), name="Ajuste"
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
        self._zero_line = self._resid.addLine(
            y=0, pen=pg.mkPen(tokens.TRACES["residual"], width=1.0)
        )
        self._resid_item = self._resid.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=3,
            symbolBrush=tokens.TRACES["fit"],
            symbolPen=None,
        )

        # Controles: modo de eje + scrubber + contador.
        self._controls = controls = QWidget()
        controls.setObjectName("curveTools")
        crow = QHBoxLayout(controls)
        crow.setContentsMargins(tokens.SPACE["1"], 0, tokens.SPACE["1"], 0)
        self._axis_mode = QComboBox()
        self._axis_mode.setAccessibleName("Eje horizontal de la curva")
        self._axis_mode.addItem("Separación", "sep")
        self._axis_mode.addItem("Indentación δ", "ind")
        self._axis_mode.currentIndexChanged.connect(self._on_axis_mode)
        self._region_check = QCheckBox("Ventana de ajuste")
        self._region_check.setToolTip("Ajustar sólo dentro de una ventana manual del eje")
        self._region_check.toggled.connect(self._on_region_toggle)
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setAccessibleName("Curva del volumen")
        self._scrubber.setMinimum(0)
        self._scrubber.valueChanged.connect(self._vm.set_curve)
        self._counter = QLabel("—")
        self._counter.setProperty("role", "readout")
        self._fit_view = QPushButton("Reencuadrar")
        self._fit_view.setToolTip("Volver a mostrar la curva y sus residuos completos")
        self._fit_view.clicked.connect(self._reset_view)
        self._export_btn = QPushButton("Exportar curva…")
        self._export_btn.setToolTip(
            "CSV científico: ajuste (con unidades) + datos separación/fuerza"
        )
        self._export_btn.clicked.connect(self._export)
        crow.addWidget(self._axis_mode)
        crow.addWidget(self._region_check)
        crow.addWidget(self._scrubber, 1)
        crow.addWidget(self._counter)
        crow.addWidget(self._fit_view)
        crow.addWidget(self._export_btn)
        self._adhesion_btn = QPushButton("Adhesión del mapa…")
        self._adhesion_btn.hide()
        self._adhesion_btn.clicked.connect(self.adhesionRequested.emit)
        crow.addWidget(self._adhesion_btn)

        self._tools = CurveViewTools(
            self._plot,
            self._resid,
            glw,
            [
                ("Aproximación", self._extend_item),
                ("Retracción", self._retract_item),
                ("Ajuste", self._fit_item),
            ],
        )
        self._tools.editStyle.connect(self.edit_style)
        self._tools.exportView.connect(self.export_view)
        self._tools.mode.currentIndexChanged.connect(
            lambda: self._region.setMovable(self._tools.mode.currentData() == "pan")
        )
        lay.addWidget(self._tools)
        self._x_name, self._y_name, self._y_unit = "Separación", "Fuerza", "nN"
        self._pin_unit = self._y_unit
        lay.addWidget(glw, 1)
        lay.addWidget(controls)

        self._update_axis_label()
        self._sync_scrubber_range()
        self._on_curve_changed(self._vm.index)
        return root

    def _reset_view(self) -> None:
        self._plot.autoRange()
        self._resid.enableAutoRange(axis=self._pg.ViewBox.YAxis)

    def set_source_name(self, name: str) -> None:
        self._tools.aliases.clear()
        self._update_axis_label()
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setText(name)
        self._source.setToolTip(name)
        self._source.setVisible(bool(name))
        self._adhesion_btn.setVisible(Path(name).suffix.lower() == ".nid")

    def set_plot_theme(self, mode: str) -> None:
        """Actualiza el lienzo abierto conservando datos, zoom y ventana de ajuste."""
        self.set_plot_appearance(Appearance(theme=mode))

    def set_plot_appearance(self, style: Appearance) -> None:
        self._appearance = style
        bg, fg, ink = style.chart_colors()
        self._tools.set_ink(fg)
        self._graphics.setBackground(bg)
        self._pinned_color = ink["residual"]
        for item in self._pinned:
            item.setPen(self._pg.mkPen(self._pinned_color, width=1))
        # Both ViewBoxes must have the same pixel origin, including after a font change.
        font = self.font()
        font.setPixelSize(self._curve_style.font_px)
        metrics = QFontMetrics(font)
        axis_width = metrics.horizontalAdvance("−0.00e−00") + 2 * metrics.height()
        for plot in (self._plot, self._resid):
            plot.getAxis("left").setWidth(axis_width)
        for plot in (self._plot, self._resid):
            for side in ("bottom", "left"):
                axis = plot.getAxis(side)
                axis.setPen(self._pg.mkPen(fg, width=self._curve_style.axis_width))
                axis.setStyle(tickFont=font)
                axis.setTextPen(fg)
                axis.setLabel(
                    text=axis.labelText,
                    units=axis.labelUnits,
                    color=fg,
                    **{"font-size": f"{self._curve_style.font_px}px"},
                )
        self._legend.setLabelTextColor(fg)
        for _, label in self._legend.items:
            label.setText(label.text, color=fg)
        for item, role, pen in zip(
            (self._extend_item, self._retract_item, self._fit_item),
            ("extend", "retract", "fit"),
            self._curve_style.pens(),
            strict=True,
        ):
            item.setPen(self._pg.mkPen(ink[role], **pen))
        self._contact_line.setPen(self._pg.mkPen(ink["contact"], style=Qt.PenStyle.DashLine))
        self._zero_line.setPen(ink["residual"])
        self._resid_item.setSymbolBrush(ink["fit"])
        tint = self._pg.mkColor(ink["fit"])
        tint.setAlpha(25)
        self._region.setBrush(tint)
        for line in self._region.lines:
            line.setPen(ink["fit"])

    def use_style_settings(self, settings: QSettings) -> None:
        self._style_settings = settings
        self._curve_style = CurveStyle.from_preference(str(settings.value("force_plot_style", "")))
        self.set_plot_appearance(self._appearance)

    def edit_style(self) -> None:
        titles = self._tools.axis_titles()
        dialog = CurveStyleDialog(self._curve_style, titles, self)
        for edit, title in zip(dialog.names, titles, strict=True):
            edit.setText(self._tools.aliases.get(title, ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._curve_style = dialog.style_value()
            if self._style_settings is not None:
                self._style_settings.setValue("force_plot_style", self._curve_style.preference())
            self._tools.set_titles((dialog.names[0].text().strip(), dialog.names[1].text().strip()))
            self.set_plot_appearance(self._appearance)

    def export_view(self) -> None:
        path, fmt = QFileDialog.getSaveFileName(
            self, "Guardar vista del gráfico", "vista", "Vector SVG (*.svg);;Imagen PNG (*.png)"
        )
        if not path:
            return
        from PyQt6.QtSvg import QSvgGenerator

        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".svg" if "svg" in fmt else ".png")
        try:
            size = self._graphics.viewport().size()
            rect = self._graphics.viewport().rect()
            file = QSaveFile(str(target))
            if not file.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(file.errorString())
            image = None
            if target.suffix.lower() == ".svg":
                svg = QSvgGenerator()
                svg.setOutputDevice(file)
                svg.setSize(size)
                svg.setViewBox(rect)
                svg.setResolution(self._graphics.logicalDpiX())
                painter = QPainter(svg)
            elif target.suffix.lower() == ".png":
                image = QImage(size * 2, QImage.Format.Format_ARGB32_Premultiplied)
                image.setDevicePixelRatio(2)
                image.fill(self._graphics.backgroundBrush().color())
                painter = QPainter(image)
            else:
                raise ValueError("Elige SVG o PNG")
            if not painter.isActive():
                raise OSError("No se pudo preparar la figura")
            try:
                self._graphics.render(painter, QRectF(rect), rect)
            finally:
                painter.end()
            if image is not None and not image.save(file, "PNG"):
                raise OSError("No se pudo escribir la imagen")
            if not file.commit():
                raise OSError(file.errorString())
            self._counter.setText("Vista guardada")
        except Exception as exc:  # noqa: BLE001 - export failures are visible in the viewer
            self._counter.setText(f"Error al guardar la vista: {exc}")

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
            "curve_index": self._vm.index,
            "recipe": json.dumps(self._vm.recipe.to_dict(), ensure_ascii=False),
            "modelo": p.get("model", ""),
            "radio_punta_nm": (p.get("tip_radius") or 0.0) * 1e9,
            "poisson": p.get("poisson", ""),
        }
        try:
            export_curve(
                curve,
                self._vm.current_results(),
                path,
                source=self._vm.source_path or "",
                extra_meta=meta,
            )
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
        self._empty.setVisible(not n)
        self._tools.clear_probe()
        for widget in (self._graphics, self._controls, self._header, self._tools):
            widget.setVisible(bool(n))
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
        self._contact = float(cp) if isinstance(cp, int | float) else None
        self._refresh_offset()
        curve = self._vm.result_curve()
        if curve is None and self._vm.n_curves:
            curve = self._vm.current_curve()
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
        item = self._plot.plot(x, y, pen=self._pg.mkPen(self._pinned_color, width=1.0))
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
            self._on_axis_mode(self._axis_mode.currentIndex())
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
        branches = [
            (item, _segment_xy(seg) if seg is not None else None)
            for item, seg in (
                (self._extend_item, curve.extend),
                (self._retract_item, curve.retract),
            )
        ]
        units = [data[2] for _, data in branches if data is not None]
        self._y_unit = next((u for u in ("nN", "nm", "V") if u in units), "V")
        self._y_name = "Fuerza" if self._y_unit == "nN" else "Deflexión"
        if self._pin_unit != self._y_unit:
            self.clear_pinned()
        self._pin_unit = self._y_unit
        labels = set()
        for item, data in branches:
            if data is None or data[2] != self._y_unit:
                item.setData([], [])
            else:
                axis, y, _, label = data
                labels.add(label)
                item.setData(self._x(axis), y)
        self._x_name = " / ".join(sorted(labels)) or "Altura"
        self._update_axis_label()
        if len(set(units)) > 1:
            self._tools.readout.setText(f"Ramas con unidades distintas · mostrando {self._y_unit}")

    def _update_axis_label(self) -> None:
        indent = self._axis_mode.currentData() == "ind"
        label = "Indentación δ" if indent and self._contact is not None else self._x_name
        self._tools.set_units(label, self._y_name, self._y_unit)

    def _sync_scrubber_range(self) -> None:
        n = self._vm.n_curves
        self._scrubber.setMaximum(max(0, n - 1))
        self._scrubber.setEnabled(n > 1)

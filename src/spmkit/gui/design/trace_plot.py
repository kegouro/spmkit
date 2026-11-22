"""Paleta semántica para los gráficos de trazas de pyqtgraph."""

from typing import Any

import pyqtgraph as pg

from spmkit.gui.design.appearance import Appearance


class TracePlot(pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__()
        self._style = Appearance()

    def set_appearance(self, style: Appearance) -> None:
        self._style = style
        bg, fg, ink = style.chart_colors()
        self.setBackground(bg)
        for side in ("left", "bottom"):
            axis = self.getPlotItem().getAxis(side)
            axis.setPen(fg)
            axis.setTextPen(fg)
            axis.label.setDefaultTextColor(pg.mkColor(fg))
        for item in self.getPlotItem().items:
            if item.property("traceRole"):
                self._paint_item(item, ink)

    def _paint_item(self, item: Any, ink: dict[str, str]) -> None:
        color = ink[item.property("traceRole")]
        width = item.property("traceWidth")
        item.setPen(pg.mkPen(color, width=width) if width else None)
        if isinstance(item, pg.PlotDataItem):
            if item.opts.get("symbol"):
                item.setSymbolBrush(color)
                item.setSymbolPen(None)
            if item.opts.get("fillLevel") is not None:
                fill = pg.mkColor(color)
                fill.setAlpha(85)
                item.setFillBrush(fill)

    def style_item(self, item: Any, role: str, width: float) -> Any:
        item.setProperty("traceRole", role)
        item.setProperty("traceWidth", width)
        self._paint_item(item, self._style.chart_colors()[2])
        return item

    def series(self, *args: Any, role: str = "fit", width: float = 1.6, **kwargs: Any) -> Any:
        item = self.getPlotItem().plot(*args, **kwargs)
        return self.style_item(item, role, width)

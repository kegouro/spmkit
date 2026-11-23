"""Inspección y escalas del visor, con eventos de ratón sobre el viewport Qt."""

import numpy as np
import pytest
from PyQt6.QtCore import QPoint, QPointF, QSettings, Qt

from spmkit.gui.design.appearance import Appearance, load_appearance, save_appearance
from spmkit.gui.panels.force_canvas import ForceCanvasPanel
from spmkit.gui.viewmodels import ForceViewModel
from spmkit.gui.widgets.curve_view_tools import AxisLimits


@pytest.fixture
def canvas(qtbot, synthetic_volume):
    vm = ForceViewModel()
    panel = ForceCanvasPanel(vm)
    qtbot.addWidget(panel)
    panel.resize(940, 600)
    panel.show()
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    qtbot.wait(200)
    panel._reset_view()
    qtbot.wait(40)
    return panel


def test_probe_click_and_display_units(canvas, qtbot):
    tools = canvas._tools
    tools.mode.setCurrentIndex(tools.mode.findData("inspect"))
    item = canvas._extend_item
    before = item.yData.copy()
    viewport = canvas._graphics.viewport()
    view = tools._view

    def point_at(i):
        scene = view.mapViewToScene(QPointF(item.xData[i], item.yData[i]))
        return canvas._graphics.mapFromScene(scene)

    i = len(before) // 2
    qtbot.mouseMove(viewport, point_at(i))
    qtbot.waitUntil(lambda: "nm" in tools.readout.text())
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=point_at(i))
    qtbot.waitUntil(lambda: tools._reference is not None)
    tools._choose_unit("x", "µm")
    tools._choose_unit("y", "pN")
    qtbot.mouseMove(viewport, point_at(i + 10))
    qtbot.waitUntil(lambda: "ΔX" in tools.readout.text())
    assert "pN" in tools.readout.text() and "µm" in tools.readout.text()
    assert canvas._plot.getAxis("left").scale == 1000
    assert canvas._resid.getAxis("bottom").scale == 0.001
    assert np.array_equal(before, item.yData)


def test_rectangle_drag_is_visual_only(canvas, qtbot):
    tools = canvas._tools
    tools.mode.setCurrentIndex(tools.mode.findData("zoom"))
    old = np.array(canvas._plot.viewRange())
    params = dict(canvas._vm.params)
    rect = tools._view.sceneBoundingRect()
    a = canvas._graphics.mapFromScene(
        rect.topLeft() + QPointF(rect.width() * 0.2, rect.height() * 0.2)
    )
    b = canvas._graphics.mapFromScene(rect.center())
    viewport = canvas._graphics.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=a)
    qtbot.mouseMove(viewport, a + QPoint(12, 12))
    qtbot.mouseMove(viewport, b)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=b)
    qtbot.waitUntil(lambda: np.ptp(canvas._plot.viewRange()[0]) < np.ptp(old[0]) * 0.8)
    assert canvas._vm.params == params
    canvas._reset_view()
    assert np.ptp(canvas._plot.viewRange()[0]) > np.ptp(old[0]) * 0.9


def test_manual_limits_convert_and_reject_invalid_ranges(canvas, qtbot):
    dlg = AxisLimits(canvas._plot, "X (µm)", "Y (pN)", (0.001, 1000.0), canvas)
    qtbot.addWidget(dlg)
    old = canvas._plot.viewRange()
    for field, text in zip(dlg._fields, ("2", "1", "0", "100"), strict=True):
        field.setText(text)
    dlg.accept()
    assert dlg._error.text() and canvas._plot.viewRange() == old
    dlg._fields[0].setText("0,5")
    dlg.accept()
    np.testing.assert_allclose(canvas._plot.viewRange(), [[500, 1000], [0, 0.1]])


def test_custom_chart_colors_survive_reload_and_redraw(canvas, qtbot, tmp_path):
    from spmkit.gui.design.trace_plot import TracePlot

    chart = TracePlot()
    qtbot.addWidget(chart)
    style = Appearance(theme="light", trace_palette="ocean", plot_background="#15232A")
    settings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    save_appearance(settings, style)
    assert load_appearance(settings) == style
    bg, _, ink = style.chart_colors()
    canvas._tools._choose_unit("y", "pN")
    ranges = canvas._plot.viewRange()
    canvas.set_plot_appearance(style)
    assert canvas._graphics.backgroundBrush().color().name() == bg.lower()
    assert canvas._plot.viewRange() == ranges
    assert canvas._plot.getAxis("left").scale == 1000
    chart.set_appearance(style)
    line = chart.series([0, 1], [2, 1])
    assert line.opts["pen"].color().name() == ink["fit"].lower()


def test_fit_y_uses_only_visible_samples(canvas):
    x, y = canvas._extend_item.getData()
    lo, hi = np.percentile(x, [35, 45])
    canvas._plot.setXRange(lo, hi, padding=0)
    canvas._plot.setYRange(-1e6, 1e6, padding=0)
    canvas._tools.fit_visible_y()
    new_x, new_y = canvas._plot.viewRange()
    np.testing.assert_allclose(new_x, [lo, hi])
    selected = y[(x >= lo) & (x <= hi)]
    assert new_y[0] <= selected.min() <= selected.max() <= new_y[1]
    assert np.ptp(new_y) < 2e6


def test_unforced_distance_and_voltage_have_physical_units():
    from spmkit.core.models import ForceSegment
    from spmkit.gui.panels.force_canvas import _segment_xy

    z = np.arange(24, dtype=np.float32) * 1e-9
    d = np.linspace(-1e-9, 0.0, len(z))
    seg = ForceSegment(
        "retract", "retract", z, np.ones(len(z)), state="deflection_m", deflection=d, separation=z
    )
    _, signal, unit, axis = _segment_xy(seg)
    np.testing.assert_allclose(signal, d * 1e9)
    assert (unit, axis) == ("nm", "Separación")
    raw = ForceSegment("extend", "approach", z, d)
    assert _segment_xy(raw)[2:] == ("V", "Altura")


def test_edit_style_and_save_current_view(canvas, qtbot, monkeypatch, tmp_path):
    import xml.etree.ElementTree as ET

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QFileDialog

    from spmkit.gui.widgets.curve_style import CurveStyleDialog

    settings = QSettings(str(tmp_path / "style.ini"), QSettings.Format.IniFormat)
    canvas.use_style_settings(settings)
    params = dict(canvas._vm.params)
    values = canvas._extend_item.yData.copy()

    def change():
        d = QApplication.activeModalWidget()
        assert isinstance(d, CurveStyleDialog)
        d.strokes[0][0].setValue(4)
        d.strokes[0][1].setCurrentText("Puntos")
        d.names[0].setText("Recorrido de ensayo")
        d.axes.setValue(3)
        d.font_size.setValue(18)
        d.accept()

    QTimer.singleShot(0, change)
    canvas._tools.editStyle.emit()
    from spmkit.gui.widgets.curve_style import CurveStyle

    assert CurveStyle.from_preference(settings.value("force_plot_style")) == canvas._curve_style
    assert CurveStyle.from_preference("broken") == CurveStyle()
    canvas._tools._choose_unit("x", "µm")
    canvas.set_plot_appearance(Appearance(theme="light"))
    assert canvas._extend_item.opts["pen"].widthF() == 4
    assert canvas._extend_item.opts["pen"].style() == Qt.PenStyle.DotLine
    assert canvas._plot.getAxis("left").pen().widthF() == 3
    assert canvas._resid.getAxis("bottom").labelText == "Recorrido de ensayo"
    assert canvas._resid.getAxis("bottom").labelUnits == "µm"
    np.testing.assert_array_equal(canvas._extend_item.yData, values)
    assert canvas._vm.params == params
    for fmt in ("svg", "png"):
        path = tmp_path / f"vista.{fmt}"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, p=path: (str(p), ""))
        canvas.export_view()
        assert canvas._counter.text() == "Vista guardada"
        if fmt == "svg":
            assert "Recorrido de ensayo" in "".join(ET.parse(path).getroot().itertext())
        else:
            assert path.read_bytes().startswith(b"\x89PNG")

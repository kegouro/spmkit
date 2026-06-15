"""Smoke test de la GUI (offscreen, vía pytest-qt).

Se omite si PyQt6 / pytest-qt no están instalados (p.ej. en el CI por defecto).
pytest-qt gestiona el ciclo de vida de la QApplication, evitando segfaults de
teardown de Qt.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")
pytest.importorskip("matplotlib")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

from spmkit.core.models import SPMChannel, SPMData  # noqa: E402
from spmkit.gui import theme  # noqa: E402
from spmkit.gui.main_window import MainWindow  # noqa: E402


def _data() -> SPMData:
    topo = SPMChannel(
        name="Z-Axis",
        data=np.random.default_rng(0).normal(size=(32, 32)),
        unit="m",
        x_range=5e-6,
        y_range=5e-6,
    )
    return SPMData(channels=(topo,), source_path="x.nid")


def test_window_constructs_and_loads(qtbot) -> None:  # type: ignore[no-untyped-def]
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.tabs.count() >= 5
    for tab in (win.viewer, win.nanomech, win.figure):
        tab.set_data(_data())
    assert win.viewer.channel_list.count() == 1


def test_theme_toggle(qtbot) -> None:  # type: ignore[no-untyped-def]
    win = MainWindow()
    qtbot.addWidget(win)
    before = win._theme
    win._toggle_theme()
    assert win._theme != before


def test_themes_render() -> None:
    assert "QTabWidget" in theme.stylesheet("dark")
    assert "QTabWidget" in theme.stylesheet("light")


def test_annotation_is_draggable(qtbot) -> None:  # type: ignore[no-untyped-def]
    from matplotlib.backend_bases import MouseEvent

    from spmkit.core.viz.figure import Annotation

    win = MainWindow()
    qtbot.addWidget(win)
    win.figure.set_data(_data())
    win.figure.channel_combo.setCurrentText("Z-Axis")
    win.figure._render()
    win.figure._spec.annotations.append(Annotation(text="x", x=0.5, y=0.5))
    win.figure._render()
    win.figure.canvas.draw()  # necesario para que contains() tenga renderer

    ann = win.figure._spec.annotations[0]
    ax = win.figure.canvas.figure.axes[0]
    px, py = ax.transAxes.transform((ann.x, ann.y))
    win.figure._on_press(MouseEvent("button_press_event", win.figure.canvas, px, py, button=1))
    assert win.figure._drag_artist is not None  # se pudo agarrar
    win.figure._on_motion(
        MouseEvent("motion_notify_event", win.figure.canvas, px + 50, py - 30, button=1)
    )
    win.figure._on_release(MouseEvent("button_release_event", win.figure.canvas, px, py, button=1))
    assert (ann.x, ann.y) != (0.5, 0.5)  # se movió

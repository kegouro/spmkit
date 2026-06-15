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
    assert win.tabs.count() == 4
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

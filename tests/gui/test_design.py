"""Tests del sistema de diseño (tokens + QSS). Puro, sin Qt."""

from __future__ import annotations

import pytest

from spmkit.gui.design import theme, tokens


def test_colors_both_modes() -> None:
    for mode in ("dark", "light"):
        c = tokens.colors(mode)
        assert c["accent"].startswith("#")
        assert {"bg", "surface", "text", "accent", "danger"} <= set(c)


def test_colors_invalid_mode_raises() -> None:
    with pytest.raises(ValueError, match="tema desconocido"):
        tokens.colors("banana")


def test_trace_hierarchy() -> None:
    assert tokens.TRACES["fit"] == tokens.colors("dark")["accent"]
    assert tokens.TRACES["contact"] == tokens.colors("dark")["accent_2"]
    assert tokens.TRACES["contact"] != tokens.TRACES["fit"]
    assert tokens.TRACES["extend"] != tokens.TRACES["fit"]
    assert tokens.TRACES["retract"] != tokens.TRACES["fit"]


def test_build_qss_substitutes_all_tokens() -> None:
    # Si faltara un $token, string.Template lanzaría KeyError.
    for mode in ("dark", "light"):
        qss = theme.build_qss(mode)
        assert "$" not in qss  # todo sustituido
        assert tokens.colors(mode)["accent"] in qss
        assert "QToolBar" in qss and "QScrollBar" in qss


def test_apply_pyqtgraph_syncs_background() -> None:
    pytest.importorskip("pyqtgraph")
    import pyqtgraph as pg

    theme.apply_pyqtgraph("dark")
    assert pg.getConfigOption("background") == tokens.colors("dark")["bg"]


def test_apply_matplotlib_syncs_facecolor() -> None:
    pytest.importorskip("matplotlib")
    import matplotlib as mpl

    theme.apply_matplotlib("light")
    assert mpl.rcParams["figure.facecolor"] == tokens.colors("light")["bg"]


def test_bundled_typeface_renders_readouts_and_plot_text(qapp):
    from matplotlib import font_manager
    from PyQt6.QtGui import QFontInfo, QFontMetricsF
    from PyQt6.QtWidgets import QLabel

    from spmkit.gui.design.typography import FAMILY

    theme.apply(qapp, font_px=14)
    label = QLabel("ΔX 1,00 µm")
    label.setProperty("role", "readout")
    label.ensurePolished()
    assert QFontInfo(label.font()).family() == FAMILY
    metrics = QFontMetricsF(label.font())
    assert metrics.horizontalAdvance("1111") == metrics.horizontalAdvance("8888")
    assert all(metrics.inFont(c) for c in "δσµ±²Δáñ")
    path = font_manager.findfont(font_manager.FontProperties(), fallback_to_default=False)
    assert font_manager.get_font(path).family_name == FAMILY

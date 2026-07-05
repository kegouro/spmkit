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
    with pytest.raises(ValueError, match="modo debe ser"):
        tokens.colors("banana")


def test_trace_hierarchy_v2() -> None:
    # Jerarquía v2: el ajuste es teal; los datos crudos son neutrales (no teal).
    assert tokens.TRACES["fit"] == "#2DD4BF"
    assert tokens.TRACES["contact"] == "#2DD4BF"
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

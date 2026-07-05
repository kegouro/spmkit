"""Tests de la marca del producto (Fathom) y su cableado en el workspace."""

from __future__ import annotations

from spmkit.gui.app_workspace import build_workspace
from spmkit.gui.design import brand


def test_brand_constants() -> None:
    assert brand.PRODUCT_NAME == "Fathom"
    assert brand.ENGINE_NAME == "spmkit"
    assert "spmkit" in brand.BYLINE
    assert brand.PRODUCT_NAME in brand.WINDOW_TITLE
    assert brand.PRODUCT_NAME in brand.about_text()


def test_workspace_title_and_about_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    assert brand.PRODUCT_NAME in ws.windowTitle()
    titles = [c.title for c in ws._commands]
    assert any("Acerca de" in t for t in titles)

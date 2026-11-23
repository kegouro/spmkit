"""Tipografía de la interfaz. Source Sans 3 v3.052R incluye cifras tabulares.

Fuentes originales y licencia OFL: adobe-fonts/source-sans, revisión
ed1808970eb3c7301c9a523bee26473ba0bb62fa.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtGui import QGuiApplication

FAMILY = "Source Sans 3"
_FONT_DIR = Path(__file__).with_name("fonts")
_FACES = ("SourceSans3-Regular.ttf", "SourceSans3-Semibold.ttf", "SourceSans3-It.ttf")


def apply_qt_font(app: QGuiApplication, font_px: int) -> None:
    from PyQt6.QtGui import QFontDatabase

    if not app.property("spmkitFontsLoaded"):
        for face in _FACES:
            QFontDatabase.addApplicationFont(str(_FONT_DIR / face))
        app.setProperty("spmkitFontsLoaded", True)
    font = app.font()
    font.setFamily(FAMILY)
    font.setPixelSize(font_px)
    if font != app.font():
        app.setFont(font)


@lru_cache(maxsize=1)
def register_matplotlib_fonts() -> None:
    from matplotlib import font_manager

    for face in _FACES:
        font_manager.fontManager.addfont(_FONT_DIR / face)


def apply_matplotlib_font() -> None:
    try:
        import matplotlib as mpl
    except ImportError:  # plotting extra is optional
        return
    register_matplotlib_fonts()
    mpl.rcParams["font.family"] = ["sans-serif"]
    mpl.rcParams["font.sans-serif"] = [FAMILY, "DejaVu Sans"]

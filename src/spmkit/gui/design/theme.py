"""Motor de tema — un token, tres destinos.

Toma los tokens (:mod:`spmkit.gui.design.tokens`) y genera de forma sincronizada:
1. el **QSS** de Qt (hoja de estilo de la app),
2. el tema de **pyqtgraph** (fondo/foreground para gráficos interactivos),
3. el estilo de **matplotlib** (rcParams para figuras de publicación).

Cambiar de claro/oscuro es hot-swap: :func:`apply` re-aplica los tres. Esto arregla
el bug histórico de que los plots no seguían el tema de la app.
"""

from __future__ import annotations

from string import Template
from typing import Any

from spmkit.gui.design import tokens

# QSS con sustitución $token (las llaves { } de QSS quedan literales).
_QSS = Template("""
* { font-family: $ui_font; font-size: 13px; }
QMainWindow, QDialog { background: $bg; }
QWidget { background: $bg; color: $text; }
QToolTip { background: $elevated; color: $text; border: 1px solid $border; padding: 4px 8px; }

QToolBar { background: $surface_2; border: none; border-bottom: 1px solid $border; padding: 6px 10px; spacing: 8px; }
QToolBar QToolButton { background: transparent; color: $text; padding: 6px 12px; border-radius: 6px; border: 1px solid transparent; }
QToolBar QToolButton:hover { background: $elevated; }
QToolBar QToolButton:checked { background: $accent_soft; color: $accent; }

QPushButton { background: $surface_2; color: $text; border: 1px solid $border_strong; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover { background: $elevated; }
QPushButton:pressed { background: $surface; }
QPushButton[primary="true"] { background: $accent; color: $on_accent; border: none; font-weight: 500; }
QPushButton[primary="true"]:hover { background: $accent_press; }
QPushButton:disabled { color: $text_faint; border-color: $border; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: $surface; color: $text; border: 1px solid $border; border-radius: 6px; padding: 5px 8px;
    selection-background-color: $accent_soft; selection-color: $text;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid $accent; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: $elevated; color: $text; border: 1px solid $border; selection-background-color: $accent_soft; }

QLabel { background: transparent; color: $text; }
QLabel[role="title"] { font-size: 15px; font-weight: 500; }
QLabel[role="muted"] { color: $text_muted; }
QLabel[role="readout"] { font-family: $mono; color: $text; }

QTreeView, QListView, QTableView { background: $surface; color: $text; border: 1px solid $border; border-radius: 8px; alternate-background-color: $surface_2; }
QTreeView::item:selected, QListView::item:selected { background: $accent_soft; color: $accent; }
QHeaderView::section { background: $surface_2; color: $text_muted; border: none; border-bottom: 1px solid $border; padding: 5px 8px; }

QTabWidget::pane { border: 1px solid $border; border-radius: 8px; top: -1px; }
QTabBar::tab { background: transparent; color: $text_muted; padding: 8px 14px; border: none; }
QTabBar::tab:selected { color: $accent; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { color: $text; }

QDockWidget { color: $text; titlebar-close-icon: none; }
QDockWidget::title { background: $surface_2; padding: 6px 10px; border-bottom: 1px solid $border; }

QMenuBar { background: $surface_2; color: $text; }
QMenuBar::item:selected { background: $elevated; }
QMenu { background: $elevated; color: $text; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: $accent_soft; color: $accent; }

QStatusBar { background: $surface; color: $text_muted; border-top: 1px solid $border; }
QStatusBar QLabel { font-family: $mono; font-size: 12px; }

QProgressBar { background: $surface_2; border: none; border-radius: 4px; height: 6px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $text_faint; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }

QSplitter::handle { background: $border; }
QSplitter::handle:hover { background: $accent; }
""")


def build_qss(mode: str = "dark") -> str:
    """Genera la hoja de estilo QSS para el modo dado (función pura, testeable)."""
    palette = tokens.colors(mode)
    return _QSS.substitute(ui_font=tokens.FONT_UI, mono=tokens.FONT_MONO, **palette)


def apply_pyqtgraph(mode: str = "dark") -> None:
    """Sincroniza el fondo/foreground de pyqtgraph con el tema (no-op si falta)."""
    try:
        import pyqtgraph as pg
    except ImportError:  # pragma: no cover - pyqtgraph es extra opcional
        return
    c = tokens.colors(mode)
    pg.setConfigOption("background", c["bg"])
    pg.setConfigOption("foreground", c["text_muted"])
    pg.setConfigOption("antialias", True)
    pg.setConfigOption("imageAxisOrder", "row-major")  # setImage([rows, cols]) sin transponer


def apply_matplotlib(mode: str = "dark") -> None:
    """Sincroniza los rcParams de matplotlib con el tema (no-op si falta)."""
    try:
        import matplotlib as mpl
        from cycler import cycler
    except ImportError:  # pragma: no cover - matplotlib es extra opcional
        return
    c = tokens.colors(mode)
    mpl.rcParams.update(
        {
            "figure.facecolor": c["bg"],
            "axes.facecolor": c["surface"],
            "axes.edgecolor": c["border"],
            "axes.labelcolor": c["text"],
            "text.color": c["text"],
            "xtick.color": c["text_muted"],
            "ytick.color": c["text_muted"],
            "grid.color": c["border"],
            "axes.prop_cycle": cycler(color=list(tokens.CATEGORICAL)),
        }
    )


def apply(app: Any, mode: str = "dark") -> None:
    """Aplica el tema completo (QSS + pyqtgraph + matplotlib) a la ``QApplication``."""
    app.setStyleSheet(build_qss(mode))
    apply_pyqtgraph(mode)
    apply_matplotlib(mode)

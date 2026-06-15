"""Sistema de temas de la GUI: estética "panel de instrumento".

Dirección de diseño: grafito casi negro (o papel cálido en claro) con un único
acento *teal* confiado, para que los datos y los colormaps sean el foco. Los
valores científicos se muestran en monoespaciado tabular (carácter de
instrumento). Tipografía nativa refinada (premium en cada plataforma).
"""

from __future__ import annotations

from typing import Any

# ---- tokens de color ------------------------------------------------------
_PALETTES = {
    "dark": {
        "bg": "#0E1116",  # grafito casi negro
        "panel": "#161B22",  # paneles
        "panel2": "#1C232D",  # controles / barras
        "elevated": "#212A36",  # hover / elevación
        "text": "#E6EDF3",
        "muted": "#8B949E",
        "accent": "#2DD4BF",  # teal de señal
        "accent_soft": "#143b38",
        "border": "#262D38",
        "danger": "#F87171",
    },
    "light": {
        "bg": "#F3F1EB",  # papel cálido
        "panel": "#FFFFFF",
        "panel2": "#EAE7DF",
        "elevated": "#E2DED4",
        "text": "#1B1F24",
        "muted": "#5C636B",
        "accent": "#0E9488",  # teal más oscuro para contraste
        "accent_soft": "#CDEDE8",
        "border": "#DAD5CA",
    },
}

# Stacks de fuente nativos refinados (no "AI slop"): el sistema de cada SO.
_UI_FONT = '-apple-system, "SF Pro Text", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif'
_MONO_FONT = '"SF Mono", "JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", monospace'

_QSS = """
* {{ font-family: {ui_font}; font-size: 13px; }}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget {{ background: {bg}; color: {text}; }}

/* ---- barra de herramientas (cabecera de instrumento) ---- */
QToolBar {{
    background: {panel2};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px 10px;
    spacing: 8px;
}}
QToolBar QToolButton {{
    background: transparent; color: {text};
    padding: 6px 12px; border-radius: 7px; border: 1px solid transparent;
}}
QToolBar QToolButton:hover {{ background: {elevated}; border-color: {border}; }}
QToolBar QToolButton:pressed {{ background: {accent_soft}; }}
QToolBar::separator {{ background: {border}; width: 1px; margin: 4px 6px; }}

/* ---- pestañas (subrayado de acento) ---- */
QTabWidget::pane {{ border: none; background: {bg}; top: -1px; }}
QTabBar {{ background: {bg}; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {muted};
    padding: 9px 20px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:hover {{ color: {text}; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; }}

/* ---- botones ---- */
QPushButton {{
    background: {panel2}; color: {text};
    border: 1px solid {border}; border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {elevated}; border-color: {accent}; }}
QPushButton:pressed {{ background: {accent_soft}; }}
QPushButton[primary="true"] {{
    background: {accent}; color: {bg}; border: 1px solid {accent}; font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {text}; border-color: {text}; }}

/* ---- entradas ---- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 7px; padding: 5px 9px;
    selection-background-color: {accent}; selection-color: {bg};
}}
QComboBox:hover, QLineEdit:hover {{ border-color: {muted}; }}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {accent};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    selection-background-color: {accent}; selection-color: {bg};
    outline: none; padding: 4px;
}}

/* ---- listas y lectores de texto ---- */
QListWidget {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 10px; padding: 4px; outline: none;
}}
QListWidget::item {{ padding: 6px 10px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {elevated}; }}
QListWidget::item:selected {{ background: {accent}; color: {bg}; }}
QTextEdit {{
    background: {panel}; color: {text};
    border: 1px solid {border}; border-radius: 10px; padding: 8px;
}}
QTextEdit[role="readout"] {{ font-family: {mono_font}; font-size: 12px; }}

/* ---- etiquetas ---- */
QLabel {{ color: {text}; background: transparent; }}
QLabel[role="title"] {{ font-size: 12px; font-weight: 700; color: {accent}; }}
QLabel[role="muted"] {{ color: {muted}; font-size: 12px; }}
QLabel[role="wordmark"] {{ font-size: 16px; font-weight: 800; color: {text}; }}

/* ---- checkbox ---- */
QCheckBox {{ spacing: 8px; color: {text}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {border};
    border-radius: 5px; background: {panel};
}}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}

/* ---- barra de estado (lectura de instrumento) ---- */
QStatusBar {{
    background: {panel2}; color: {muted};
    border-top: 1px solid {border};
}}
QStatusBar QLabel {{ color: {muted}; }}

/* ---- splitter / scrollbars ---- */
QSplitter::handle {{ background: {border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QToolTip {{
    background: {panel2}; color: {text};
    border: 1px solid {accent}; border-radius: 6px; padding: 4px 8px;
}}
"""


def palette(name: str) -> dict[str, str]:
    """Paleta de colores del tema (también para los lienzos de matplotlib)."""
    return _PALETTES.get(name, _PALETTES["dark"])


def stylesheet(name: str = "dark") -> str:
    """Genera el QSS del tema indicado."""
    return _QSS.format(ui_font=_UI_FONT, mono_font=_MONO_FONT, **palette(name))


def apply_theme(app: Any, name: str = "dark") -> None:
    """Aplica el tema a la QApplication."""
    app.setStyleSheet(stylesheet(name))


def mpl_style(name: str = "dark") -> dict[str, Any]:
    """Parámetros rcParams de matplotlib coherentes con el tema."""
    p = palette(name)
    return {
        "figure.facecolor": p["panel"],
        "axes.facecolor": p["panel"],
        "savefig.facecolor": p["panel"],
        "text.color": p["text"],
        "axes.labelcolor": p["text"],
        "axes.edgecolor": p["border"],
        "xtick.color": p["muted"],
        "ytick.color": p["muted"],
        "axes.titlecolor": p["text"],
    }

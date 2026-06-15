"""Temas visuales de la GUI (claro / oscuro) vía hojas de estilo Qt (QSS).

Paleta científica de alto contraste pensada para ver imágenes AFM sin que el
cromado de la interfaz compita con los datos.
"""

from __future__ import annotations

from typing import Any

# Paletas: (fondo, panel, texto, acento, borde, panel2)
_PALETTES = {
    "dark": {
        "bg": "#1b1e23",
        "panel": "#23272e",
        "panel2": "#2b3038",
        "text": "#e6e6e6",
        "muted": "#9aa0a6",
        "accent": "#4ea1ff",
        "border": "#3a3f47",
    },
    "light": {
        "bg": "#f5f6f8",
        "panel": "#ffffff",
        "panel2": "#eef0f3",
        "text": "#1a1a1a",
        "muted": "#5a5f66",
        "accent": "#1769d6",
        "border": "#d0d4da",
    },
}

_QSS = """
* {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 13px; }}
QMainWindow, QWidget {{ background: {bg}; color: {text}; }}
QTabWidget::pane {{ border: 1px solid {border}; background: {panel}; }}
QTabBar::tab {{
    background: {panel2}; color: {muted}; padding: 7px 16px; border: 1px solid {border};
    border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{ background: {panel}; color: {text}; border-bottom: 2px solid {accent}; }}
QToolBar {{ background: {panel2}; border-bottom: 1px solid {border}; spacing: 6px; padding: 4px; }}
QPushButton {{
    background: {panel2}; color: {text}; border: 1px solid {border};
    border-radius: 6px; padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:pressed {{ background: {accent}; color: white; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {panel}; color: {text}; border: 1px solid {border};
    border-radius: 5px; padding: 4px 8px;
}}
QComboBox:hover, QLineEdit:focus {{ border-color: {accent}; }}
QListWidget, QTextEdit {{
    background: {panel}; color: {text}; border: 1px solid {border}; border-radius: 6px;
}}
QListWidget::item:selected {{ background: {accent}; color: white; }}
QLabel {{ color: {text}; }}
QLabel[role="title"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="muted"] {{ color: {muted}; }}
QStatusBar {{ background: {panel2}; color: {muted}; border-top: 1px solid {border}; }}
QSplitter::handle {{ background: {border}; }}
QScrollBar:vertical {{ background: {panel}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 6px; min-height: 24px; }}
"""


def palette(name: str) -> dict[str, str]:
    """Devuelve la paleta de colores del tema (para los lienzos matplotlib)."""
    return _PALETTES.get(name, _PALETTES["dark"])


def stylesheet(name: str = "dark") -> str:
    """Genera el QSS del tema indicado."""
    return _QSS.format(**palette(name))


def apply_theme(app: Any, name: str = "dark") -> None:
    """Aplica el tema a la QApplication."""
    app.setStyleSheet(stylesheet(name))

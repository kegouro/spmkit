"""Punto de entrada de la GUI de spmkit."""

from __future__ import annotations

import sys


def run() -> None:
    """Lanza la aplicación gráfica."""
    from PyQt6 import QtWidgets

    from spmkit.gui import theme
    from spmkit.gui.main_window import MainWindow

    app = QtWidgets.QApplication(sys.argv)
    theme.apply_theme(app, "dark")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()

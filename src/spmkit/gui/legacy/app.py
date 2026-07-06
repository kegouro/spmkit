"""Punto de entrada de la GUI **clásica** (legacy) de spmkit — las 7 pestañas."""

from __future__ import annotations

import sys


def run() -> None:
    """Lanza la app clásica (legacy). El default de ``spmkit gui`` es Fathom."""
    from PyQt6 import QtCore, QtWidgets

    from spmkit.gui.legacy import theme
    from spmkit.gui.legacy.main_window import MainWindow

    app = QtWidgets.QApplication(sys.argv)
    saved_theme = QtCore.QSettings("SPMLabUTFSM", "spmkit").value("theme", "dark", type=str)
    theme.apply_theme(app, saved_theme)
    window = MainWindow()
    window.show()
    window.show_welcome()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()

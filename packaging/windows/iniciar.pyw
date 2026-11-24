"""Entry point for the portable Windows edition of Fathom."""
import ctypes
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import traceback


def main():
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import QApplication
    from spmkit.gui.app_workspace import build_workspace

    root = Path(__file__).resolve().parent.parent
    app = QApplication(sys.argv)
    ws = build_workspace(open_path=sys.argv[1] if len(sys.argv) > 1 else None, persist=True)
    ws.add_toolbar_action("Guía NID", lambda: QDesktopServices.openUrl(
        QUrl.fromLocalFile(str(root / "02 - GUIA NID.pdf"))))
    ws.add_toolbar_action("Práctica NID", lambda: QDesktopServices.openUrl(
        QUrl.fromLocalFile(str(root / "Practica"))))
    ws.show()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        code = main()
    except Exception:
        detail = traceback.format_exc()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="Fathom-arranque-",
                                             encoding="utf-8", delete=False) as f:
                f.write(detail)
            detail = "Diagnóstico de inicio: " + f.name
        except OSError:
            pass
        ctypes.windll.user32.MessageBoxW(0, "Compruebe que extrajo todo el ZIP.\n" + detail,
                                        "Fathom · Error al abrir", 0x10)
        code = 1
    raise SystemExit(code)

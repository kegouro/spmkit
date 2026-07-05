"""Panel de log — recoge los mensajes de estado de los ViewModels en un solo lugar.

Los ajustes fallidos, los mapas y batches que terminan o rompen emiten ``statusChanged``;
este panel los acumula para tener trazabilidad (útil sobre todo en la perspectiva batch,
donde un archivo malo no aborta el lote pero conviene verlo).
"""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from spmkit.gui.panels.base import Panel


class LogPanel(Panel):
    """Panel-dock que registra los ``statusChanged`` de varios ViewModels."""

    title = "Log"

    def __init__(self, sources: Iterable[QObject], parent: QWidget | None = None) -> None:
        self._sources = list(sources)
        super().__init__(parent)
        for src in self._sources:
            signal = getattr(src, "statusChanged", None)
            if signal is not None:
                signal.connect(self.append)

    def build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setSpacing(6)

        bar = QHBoxLayout()
        clear = QPushButton("Limpiar")
        clear.clicked.connect(self.clear)
        bar.addStretch(1)
        bar.addWidget(clear)
        lay.addLayout(bar)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)  # evita crecer sin límite
        lay.addWidget(self._text, 1)
        return root

    def append(self, message: str) -> None:
        self._text.appendPlainText(message)

    def clear(self) -> None:
        self._text.clear()

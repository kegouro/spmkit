"""Barra de estado con progreso global cancelable.

Se conecta a las señales de un :class:`~spmkit.gui.runtime.tasks.Task` para mostrar el
progreso de cualquier operación pesada (ajustes, mapas, cargas) sin bloquear la UI, con
un botón de cancelar.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QWidget,
)


class ProgressStatusBar(QStatusBar):
    """Barra de estado: mensaje a la izquierda, progreso + cancelar a la derecha."""

    cancelRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._message = QLabel("")
        self._message.setProperty("role", "readout")
        self.addWidget(self._message, 1)

        self._progress_widget = QWidget()
        row = QHBoxLayout(self._progress_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self._pct = QLabel("")
        self._pct.setProperty("role", "muted")
        self._bar = QProgressBar()
        self._bar.setFixedWidth(160)
        self._bar.setTextVisible(False)
        self._cancel = QPushButton("Cancelar")
        self._cancel.clicked.connect(self.cancelRequested)
        for widget in (self._pct, self._bar, self._cancel):
            row.addWidget(widget)
        self.addPermanentWidget(self._progress_widget)
        self._progress_widget.hide()

    def set_message(self, text: str) -> None:
        self._message.setText(text)

    def start_progress(self, label: str = "") -> None:
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._pct.setText(label)
        self._progress_widget.show()

    def set_progress(self, fraction: float, message: str = "") -> None:
        pct = int(round(fraction * 100))
        self._bar.setValue(pct)
        self._pct.setText(f"{pct}%  {message}".strip())

    def end_progress(self) -> None:
        self._progress_widget.hide()

    @property
    def progress_visible(self) -> bool:
        return self._progress_widget.isVisible()

    def bind_task(self, task: Any) -> None:
        """Conecta las señales de un ``Task``: progreso, fin y cancelación."""
        task.signals.progress.connect(self.set_progress)
        task.signals.finished.connect(self.end_progress)
        self.cancelRequested.connect(task.cancel)
        self.start_progress()

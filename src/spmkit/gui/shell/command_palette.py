"""Paleta de comandos (⌘K) — búsqueda difusa de todas las acciones."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from spmkit.gui.shell.fuzzy import rank


@dataclass
class Command:
    """Una acción invocable desde la paleta."""

    title: str
    callback: Callable[[], None]
    shortcut: str = ""


class CommandPalette(QDialog):
    """Diálogo modal con un campo de búsqueda y una lista difusa de comandos."""

    def __init__(self, commands: Iterable[Command], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Comandos")
        self.setModal(True)
        self.resize(480, 360)
        self._commands = list(commands)

        layout = QVBoxLayout(self)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Buscar comando…")
        self._list = QListWidget()
        layout.addWidget(self._input)
        layout.addWidget(self._list)

        self._input.textChanged.connect(self._filter)
        self._input.returnPressed.connect(self._run_current)
        self._list.itemActivated.connect(lambda _: self._run_current())
        self._filter("")
        self._input.setFocus()

    def visible_titles(self) -> list[str]:
        """Títulos actualmente listados (para tests y navegación)."""
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _filter(self, text: str) -> None:
        self._list.clear()
        titles = [c.title for c in self._commands]
        for idx, _score in rank(text, titles):
            cmd = self._commands[idx]
            label = f"{cmd.title}    {cmd.shortcut}".rstrip() if cmd.shortcut else cmd.title
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _run_current(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        self.accept()
        self._commands[idx].callback()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802 - override Qt
        if event is not None and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._list.keyPressEvent(event)
            return
        super().keyPressEvent(event)

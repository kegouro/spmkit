"""Navegador de curvas — lista las curvas del force-volume y permite saltar entre ellas.

Doble binding con el :class:`ForceViewModel`: seleccionar una fila llama a
``set_curve``; cuando la VM cambia de curva (scrubber, teclado, paleta), la selección
se sincroniza sin lazos de señales. Los botones ‹ › avanzan de a una.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel


class NavigatorPanel(Panel):
    """Panel-dock con la lista de curvas del force-volume activo."""

    title = "Navegador"

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.volumeChanged.connect(self._rebuild_list)
        vm.curveChanged.connect(self._select_row)

    def build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setSpacing(6)

        nav = QHBoxLayout()
        self._prev = QPushButton("‹")
        self._next = QPushButton("›")
        self._prev.clicked.connect(lambda: self._step(-1))
        self._next.clicked.connect(lambda: self._step(+1))
        self._count = QLabel("sin datos")
        self._count.setProperty("role", "muted")
        nav.addWidget(self._prev)
        nav.addWidget(self._next)
        nav.addStretch(1)
        nav.addWidget(self._count)
        lay.addLayout(nav)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self._list, 1)

        self._rebuild_list(self._vm.n_curves)
        return root

    # ---- binding ----
    def _rebuild_list(self, n_curves: int) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for i in range(n_curves):
            pos = self._position_label(i)
            self._list.addItem(f"Curva {i + 1:>4}{pos}")
        self._list.blockSignals(False)
        self._count.setText(f"{n_curves} curvas" if n_curves else "sin datos")
        self._select_row(self._vm.index)

    def _position_label(self, index: int) -> str:
        """Etiqueta ‹x, y› en µm si la curva trae posición (force-map); si no, vacío."""
        try:
            pos = self._vm.current_curve().position if index == self._vm.index else None
        except Exception:  # noqa: BLE001 - la lista no debe romperse por una curva mala
            return ""
        if pos is None:
            return ""
        return f"   ({pos[0] * 1e6:.1f}, {pos[1] * 1e6:.1f}) µm"

    def _select_row(self, index: int) -> None:
        if 0 <= index < self._list.count() and index != self._list.currentRow():
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.blockSignals(False)

    def _on_row(self, row: int) -> None:
        if row >= 0:
            self._vm.set_curve(row)

    def _step(self, delta: int) -> None:
        self._vm.set_curve(self._vm.index + delta)

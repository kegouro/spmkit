"""Navegador de datos — lista lo cargado (curvas de fuerza **o** canales de imagen).

Panel "Datos" compartido por todas las perspectivas. Es *dual-hub*: si hay un force-volume
activo lista sus curvas (doble binding con :class:`ForceViewModel`), y si en cambio hay una
imagen cargada lista sus canales (binding con :class:`ImageViewModel`). Seleccionar una fila
cambia la curva/canal activo; los botones ‹ › avanzan de a uno. Sin lazos de señales.
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
from spmkit.gui.viewmodels import ForceViewModel, ImageViewModel


class NavigatorPanel(Panel):
    """Panel-dock con la lista de curvas del force-volume o de canales de imagen activos."""

    title = "Navegador"

    def __init__(
        self,
        vm: ForceViewModel,
        image_vm: ImageViewModel,
        parent: QWidget | None = None,
    ) -> None:
        self._vm = vm
        self._image_vm = image_vm
        self._mode = "force"  # "force" (curvas) | "image" (canales)
        super().__init__(parent)
        vm.volumeChanged.connect(lambda _n: self._sync())
        vm.curveChanged.connect(lambda i: self._select_row(i, "force"))
        image_vm.dataChanged.connect(lambda _names: self._sync())
        image_vm.channelChanged.connect(lambda _n: self._select_row(self._image_index(), "image"))

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

        self._sync()  # hidrata el estado ya cargado (no espera solo señales futuras)
        return root

    def refresh(self) -> None:
        """Re-sincroniza con el estado actual (el shell lo llama al activar la perspectiva)."""
        self._sync()

    # ---- binding ----
    def _sync(self) -> None:
        """Reconstruye la lista según lo cargado: curvas de fuerza o canales de imagen."""
        if self._vm.n_curves > 0:
            self._mode = "force"
            items = [f"Curva {i + 1:>4}{self._position_label(i)}" for i in range(self._vm.n_curves)]
            current, count = self._vm.index, f"{self._vm.n_curves} curvas"
        elif self._image_vm.names:
            self._mode = "image"
            items = [f"Canal · {n}" for n in self._image_vm.names]
            current, count = self._image_index(), f"{len(items)} canales"
        else:
            self._mode = "force"
            items, current, count = [], 0, "sin datos"

        self._list.blockSignals(True)
        self._list.clear()
        self._list.addItems(items)
        if 0 <= current < len(items):
            self._list.setCurrentRow(current)
        self._list.blockSignals(False)
        self._count.setText(count)

    def _image_index(self) -> int:
        names = self._image_vm.names
        ch = self._image_vm.channel
        return names.index(ch) if ch in names else 0

    def _position_label(self, index: int) -> str:
        """Etiqueta ‹x, y› en µm si la curva trae posición (force-map); si no, vacío."""
        try:
            pos = self._vm.current_curve().position if index == self._vm.index else None
        except Exception:  # noqa: BLE001 - la lista no debe romperse por una curva mala
            return ""
        if pos is None:
            return ""
        return f"   ({pos[0] * 1e6:.1f}, {pos[1] * 1e6:.1f}) µm"

    def _select_row(self, index: int, mode: str) -> None:
        if mode != self._mode:
            return
        if 0 <= index < self._list.count() and index != self._list.currentRow():
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.blockSignals(False)

    def _on_row(self, row: int) -> None:
        if row < 0:
            return
        if self._mode == "image":
            names = self._image_vm.names
            if 0 <= row < len(names):
                self._image_vm.set_channel(names[row])
        else:
            self._vm.set_curve(row)

    def _step(self, delta: int) -> None:
        row = self._list.currentRow() + delta
        if 0 <= row < self._list.count():
            self._list.setCurrentRow(row)  # dispara _on_row → cambia curva/canal

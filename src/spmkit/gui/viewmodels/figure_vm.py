"""ViewModel del editor de figuras — spec de publicación + anotaciones.

Modelo editable de una figura (``FigureSpec`` + lista de ``Annotation``) sobre el canal
crudo del hub de imagen compartido (:class:`ImageViewModel`). El panel sincroniza el
formulario con este estado; el core puro (``core.viz.figure``) hace el render.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.models import SPMChannel
from spmkit.core.viz.figure import Annotation, FigureSpec
from spmkit.gui.viewmodels.image_vm import ImageViewModel


class FigureViewModel(QObject):
    """Estado observable del editor de figuras (spec + anotaciones)."""

    dataChanged = pyqtSignal(list)  # nombres de canales disponibles
    changed = pyqtSignal()  # spec o anotaciones editadas → re-render

    def __init__(self, image_vm: ImageViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._image_vm = image_vm
        self._spec = FigureSpec()
        self._annotations: list[Annotation] = []
        self._index = 0  # canal activo por posición (distingue nombres duplicados)
        image_vm.dataChanged.connect(self._on_data)

    # ---- estado ----
    @property
    def names(self) -> list[str]:
        return self._image_vm.names

    def labels(self) -> list[str]:
        """Etiquetas desambiguadas de los canales, para el selector."""
        return self._image_vm.labels()

    @property
    def spec(self) -> FigureSpec:
        return self._spec

    @property
    def annotations(self) -> list[Annotation]:
        return self._annotations

    @property
    def channel(self) -> str:
        ch = self._image_vm.raw_channel_at(self._index)
        return ch.name if ch is not None else ""

    @property
    def index(self) -> int:
        return self._index

    def current_channel(self) -> SPMChannel | None:
        """Canal crudo activo (por posición) desde el hub de imagen (o ``None``)."""
        return self._image_vm.raw_channel_at(self._index)

    # ---- mutaciones ----
    def set_index(self, index: int) -> None:
        """Selecciona el canal por **posición** (fuente única de identidad)."""
        if index >= 0 and index != self._index:
            self._index = index
            self.changed.emit()

    def set_channel(self, name: str) -> None:
        """Compatibilidad: selecciona por nombre (primer match)."""
        for i, n in enumerate(self._image_vm.names):
            if n == name:
                self.set_index(i)
                return

    def update_spec(self, **kwargs: Any) -> None:
        """Reemplaza campos del ``FigureSpec`` y notifica re-render."""
        self._spec = replace(self._spec, **kwargs)
        self.changed.emit()

    def add_annotation(self, ann: Annotation) -> None:
        self._annotations.append(ann)
        self.changed.emit()

    def remove_annotation(self, ann: Annotation) -> None:
        if ann in self._annotations:
            self._annotations.remove(ann)
            self.changed.emit()

    def _on_data(self, names: list) -> None:
        self._index = 0
        self.dataChanged.emit(list(names))
        self.changed.emit()

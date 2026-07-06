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
        self._channel = ""
        image_vm.dataChanged.connect(self._on_data)

    # ---- estado ----
    @property
    def names(self) -> list[str]:
        return self._image_vm.names

    @property
    def spec(self) -> FigureSpec:
        return self._spec

    @property
    def annotations(self) -> list[Annotation]:
        return self._annotations

    @property
    def channel(self) -> str:
        return self._channel

    def current_channel(self) -> SPMChannel | None:
        """Canal crudo activo desde el hub de imagen (o ``None``)."""
        return self._image_vm.raw_channel(self._channel)

    # ---- mutaciones ----
    def set_channel(self, name: str) -> None:
        if name and name != self._channel:
            self._channel = name
            self.changed.emit()

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
        self._channel = str(names[0]) if names else ""
        self.dataChanged.emit(list(names))
        self.changed.emit()

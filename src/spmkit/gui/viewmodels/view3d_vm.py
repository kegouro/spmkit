"""ViewModel de la vista 3D — superficie de topografía para presentaciones.

Guarda los parámetros de la superficie (canal, colormap, exageración Z, iluminación)
sobre el canal crudo del hub de imagen compartido (:class:`ImageViewModel`). El render
matplotlib (``plot_surface``/hillshade) vive en el panel; aquí sólo el estado.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.models import SPMChannel
from spmkit.gui.viewmodels.image_vm import ImageViewModel

#: Colormaps ofrecidos en el selector 3D.
CMAPS: tuple[str, ...] = ("gold", "viridis", "inferno", "afmhot", "gray")


class View3DViewModel(QObject):
    """Estado observable de la vista 3D de superficie."""

    dataChanged = pyqtSignal(list)  # nombres de canales disponibles
    changed = pyqtSignal()  # parámetro editado → re-render

    def __init__(self, image_vm: ImageViewModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._image_vm = image_vm
        self._channel = ""
        self._cmap = "gold"
        self._z_exag = 50
        self._hillshade = True
        image_vm.dataChanged.connect(self._on_data)

    # ---- estado ----
    @property
    def names(self) -> list[str]:
        return self._image_vm.names

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def cmap(self) -> str:
        return self._cmap

    @property
    def z_exag(self) -> int:
        return self._z_exag

    @property
    def hillshade(self) -> bool:
        return self._hillshade

    def current_channel(self) -> SPMChannel | None:
        """Canal crudo activo desde el hub de imagen (o ``None``)."""
        return self._image_vm.raw_channel(self._channel)

    # ---- mutaciones ----
    def set_channel(self, name: str) -> None:
        if name and name != self._channel:
            self._channel = name
            self.changed.emit()

    def set_cmap(self, name: str) -> None:
        if name and name != self._cmap:
            self._cmap = name
            self.changed.emit()

    def set_z_exag(self, value: int) -> None:
        if value != self._z_exag:
            self._z_exag = value
            self.changed.emit()

    def set_hillshade(self, on: bool) -> None:
        if on != self._hillshade:
            self._hillshade = on
            self.changed.emit()

    def _on_data(self, names: list) -> None:
        # Prefiere un canal de altura ("Z-Axis") si existe; si no, el primero.
        preferred = next((str(n) for n in names if "Z-Axis" in str(n)), None)
        self._channel = preferred or (str(names[0]) if names else "")
        self.dataChanged.emit(list(names))
        self.changed.emit()

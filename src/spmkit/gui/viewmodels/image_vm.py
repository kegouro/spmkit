"""ViewModel de imágenes SPM — canal activo + nivelado, para la perspectiva Imagen.

Un visor básico (no un clon de Gwyddion): abrir un ``.nid``/``.nhf``/``.gwy``, elegir
canal, nivelar (plano/polinomio) y ver rugosidad. Reutiliza el ``core`` puro
(``load``, ``leveling``, ``roughness``); la perspectiva de fuerza sigue siendo la joya.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import leveling, roughness
from spmkit.core.models import SPMChannel, SPMData


class ImageViewModel(QObject):
    """Estado observable de la perspectiva de imagen."""

    dataChanged = pyqtSignal(list)  # nombres de canales del dato cargado
    channelChanged = pyqtSignal(str)  # canal activo (o re-render tras nivelar)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: SPMData | None = None
        self._channel = ""
        self._leveling = "plane"

    @property
    def names(self) -> list[str]:
        return list(self._data.names) if self._data is not None else []

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def leveling(self) -> str:
        return self._leveling

    def set_data(self, data: SPMData) -> None:
        self._data = data
        names = list(data.names)
        self._channel = names[0] if names else ""
        self.dataChanged.emit(names)
        self.channelChanged.emit(self._channel)

    def set_channel(self, name: str) -> None:
        if name and name != self._channel:
            self._channel = name
            self.channelChanged.emit(name)

    def set_leveling(self, mode: str) -> None:
        if mode != self._leveling:
            self._leveling = mode
            self.channelChanged.emit(self._channel)  # re-render con el nivelado nuevo

    def current_channel(self) -> SPMChannel | None:
        """Canal activo con el nivelado aplicado (o crudo si el nivelado falla)."""
        if self._data is None or not self._channel:
            return None
        ch = self._data[self._channel]
        try:
            if self._leveling == "plane":
                return leveling.plane_fit(ch)
            if self._leveling == "poly":
                return leveling.polynomial(ch, order=2)
        except Exception:  # noqa: BLE001 - nivelado opcional; si falla, se muestra crudo
            return ch
        return ch

    def roughness(self) -> Any:
        """Estadística de rugosidad del canal nivelado (o ``None``)."""
        ch = self.current_channel()
        if ch is None:
            return None
        try:
            return roughness.statistics(ch)
        except Exception:  # noqa: BLE001 - no toda imagen es de altura
            return None

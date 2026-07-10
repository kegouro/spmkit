"""ViewModel de imágenes SPM — canal activo + nivelado + perfil, perspectiva Imagen.

Visor de imagen con paridad de análisis (nivelado plano/polinomio/filas, perfil de línea,
rugosidad y KPFM). Reutiliza el ``core`` puro (``leveling``, ``roughness``, ``kpfm``,
``profiles``); es también el **hub de imagen** que alimentan figura y 3D. La perspectiva
de fuerza sigue siendo la joya.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from spmkit.core.analysis import kpfm, leveling, roughness
from spmkit.core.analysis.profiles import Profile
from spmkit.core.analysis.profiles import line as profile_line
from spmkit.core.models import SPMChannel, SPMData


class ImageViewModel(QObject):
    """Estado observable de la perspectiva de imagen."""

    dataChanged = pyqtSignal(list)  # nombres de canales del dato cargado
    channelChanged = pyqtSignal(str)  # canal activo (o re-render tras nivelar)
    profileChanged = pyqtSignal(object)  # Profile del último trazo (o None)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: SPMData | None = None
        self._channel = ""
        self._leveling = "plane"
        self._poly_order = 2  # grado del nivelado polinómico
        self._row_stat = "median"  # estadístico del alineado por filas
        self._tip_work_function: float | None = None  # eV; para phi de la muestra (KPFM)
        self._last_profile: Profile | None = None

    @property
    def data(self) -> SPMData | None:
        """El :class:`SPMData` cargado (hub compartido con figura/3D), o ``None``."""
        return self._data

    @property
    def names(self) -> list[str]:
        return list(self._data.names) if self._data is not None else []

    def raw_channel(self, name: str) -> SPMChannel | None:
        """Canal **crudo** por nombre (sin nivelar), para figura/3D. ``None`` si no existe."""
        if self._data is None or not name:
            return None
        try:
            return self._data[name]
        except KeyError:
            return None

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

    @property
    def poly_order(self) -> int:
        return self._poly_order

    @property
    def row_stat(self) -> str:
        return self._row_stat

    def set_poly_order(self, order: int) -> None:
        """Grado del nivelado polinómico (re-renderiza si está activo)."""
        if order != self._poly_order and order >= 1:
            self._poly_order = int(order)
            if self._leveling == "poly":
                self.channelChanged.emit(self._channel)

    def set_row_stat(self, stat: str) -> None:
        """Estadístico del alineado por filas (``"median"``/``"mean"``)."""
        if stat != self._row_stat and stat in ("median", "mean"):
            self._row_stat = stat
            if self._leveling == "rows":
                self.channelChanged.emit(self._channel)

    @property
    def tip_work_function(self) -> float | None:
        return self._tip_work_function

    def set_tip_work_function(self, ev: float | None) -> None:
        """Función de trabajo de la punta (eV); ``None``/0 = no calcular la de la muestra."""
        value = None if not ev else float(ev)
        if value != self._tip_work_function:
            self._tip_work_function = value
            self.channelChanged.emit(self._channel)  # re-analiza KPFM

    def current_channel(self) -> SPMChannel | None:
        """Canal activo con el nivelado aplicado (o crudo si el nivelado falla)."""
        if self._data is None or not self._channel:
            return None
        ch = self._data[self._channel]
        try:
            if self._leveling == "plane":
                return leveling.plane_fit(ch)
            if self._leveling == "poly":
                return leveling.polynomial(ch, order=self._poly_order)
            if self._leveling == "rows":
                return leveling.align_rows(ch, method=self._row_stat)
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

    def kpfm(self) -> Any:
        """CPD/KPFM del canal nivelado si es de potencial (unidad ``V``); si no, ``None``.

        Si se fijó :meth:`set_tip_work_function`, también calcula la función de trabajo de
        la muestra (``phi_sample = phi_tip − V_CPD``).
        """
        ch = self.current_channel()
        if ch is None or ch.unit.upper() != "V":
            return None
        try:
            return kpfm.statistics(ch, tip_work_function=self._tip_work_function)
        except Exception:  # noqa: BLE001 - análisis opcional
            return None

    @property
    def last_profile(self) -> Profile | None:
        return self._last_profile

    def profile(self, p0: tuple[float, float], p1: tuple[float, float]) -> Profile | None:
        """Perfil de línea entre dos puntos en píxeles ``(col, row)``; emite ``profileChanged``.

        Devuelve ``None`` (sin emitir) si no hay canal o el trazo queda fuera de rango
        durante el arrastre.
        """
        ch = self.current_channel()
        if ch is None:
            return None
        try:
            prof = profile_line(ch, p0, p1)
        except Exception:  # noqa: BLE001 - fuera de rango durante el arrastre
            return None
        self._last_profile = prof
        self.profileChanged.emit(prof)
        return prof

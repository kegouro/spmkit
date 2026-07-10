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


def channel_labels(data: SPMData | None) -> list[str]:
    """Etiquetas **únicas** por canal, para los selectores de la GUI.

    Los ``.nid`` de NanoSurf traen canales con el mismo ``Dim2Name`` (p. ej. ``Z-Axis``
    forward + backward, o ``Amplitude Spectral Density`` de los frames FFT/Fit). Como la
    GUI selecciona por posición, aquí desambiguamos el nombre con el frame/dirección **solo
    cuando colisiona**, para que el usuario distinga —y pueda abrir— cada canal.
    """
    if data is None:
        return []
    names = [c.name for c in data.channels]
    labels: list[str] = []
    for i, c in enumerate(data.channels):
        if names.count(c.name) > 1:
            tag = c.group or c.direction or str(i)
            labels.append(f"{c.name} · {tag}")
        else:
            labels.append(c.name)
    return labels


class ImageViewModel(QObject):
    """Estado observable de la perspectiva de imagen."""

    dataChanged = pyqtSignal(list)  # nombres de canales del dato cargado
    channelChanged = pyqtSignal(str)  # canal activo (o re-render tras nivelar)
    profileChanged = pyqtSignal(object)  # Profile del último trazo (o None)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: SPMData | None = None
        self._channel_index = 0  # identidad del canal activo (por posición, no por nombre)
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

    def labels(self) -> list[str]:
        """Etiquetas **desambiguadas** para los selectores (ver :func:`channel_labels`)."""
        return channel_labels(self._data)

    def raw_channel(self, name: str) -> SPMChannel | None:
        """Canal **crudo** por nombre (sin nivelar); primer match. Ver :meth:`raw_channel_at`."""
        if self._data is None or not name:
            return None
        try:
            return self._data[name]
        except KeyError:
            return None

    def raw_channel_at(self, index: int) -> SPMChannel | None:
        """Canal **crudo** por posición (sin nivelar), para figura/3D. Distingue duplicados."""
        if self._data is None or not (0 <= index < len(self._data.channels)):
            return None
        return self._data.channels[index]

    @property
    def channel(self) -> str:
        """Nombre del canal activo (por posición). Cadena vacía si no hay datos."""
        ch = self.raw_channel_at(self._channel_index)
        return ch.name if ch is not None else ""

    @property
    def current_index(self) -> int:
        return self._channel_index

    @property
    def leveling(self) -> str:
        return self._leveling

    def set_data(self, data: SPMData) -> None:
        self._data = data
        self._channel_index = 0
        self.dataChanged.emit(list(data.names))
        self.channelChanged.emit(self.channel)

    def set_channel_index(self, index: int) -> None:
        """Selecciona el canal activo por **posición** (fuente única de identidad)."""
        if self._data is None or not (0 <= index < len(self._data.channels)):
            return
        if index != self._channel_index:
            self._channel_index = index
            self.channelChanged.emit(self.channel)

    def set_channel(self, name: str) -> None:
        """Selecciona por nombre (primer match). Compat; prefiere :meth:`set_channel_index`."""
        if self._data is None or not name:
            return
        for i, c in enumerate(self._data.channels):
            if c.name == name:
                self.set_channel_index(i)
                return

    def set_leveling(self, mode: str) -> None:
        if mode != self._leveling:
            self._leveling = mode
            self.channelChanged.emit(self.channel)  # re-render con el nivelado nuevo

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
                self.channelChanged.emit(self.channel)

    def set_row_stat(self, stat: str) -> None:
        """Estadístico del alineado por filas (``"median"``/``"mean"``)."""
        if stat != self._row_stat and stat in ("median", "mean"):
            self._row_stat = stat
            if self._leveling == "rows":
                self.channelChanged.emit(self.channel)

    @property
    def tip_work_function(self) -> float | None:
        return self._tip_work_function

    def set_tip_work_function(self, ev: float | None) -> None:
        """Función de trabajo de la punta (eV); ``None``/0 = no calcular la de la muestra."""
        value = None if not ev else float(ev)
        if value != self._tip_work_function:
            self._tip_work_function = value
            self.channelChanged.emit(self.channel)  # re-analiza KPFM

    def current_channel(self) -> SPMChannel | None:
        """Canal activo (por posición) con el nivelado aplicado (o crudo si falla)."""
        ch = self.raw_channel_at(self._channel_index)
        if ch is None:
            return None
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

"""Modelo de datos de espectroscopía de fuerza (curvas de fuerza / force-volume).

Extiende el dominio SPM con curvas de fuerza calibrables. Cada curva tiene uno o
más segmentos (extend / retract / pause / modulation) que guardan **siempre** los
canales crudos (para poder recalibrar) y, a medida que el pipeline avanza, los
derivados (deflexión en m, fuerza en N, separación punta-muestra en m). El campo
``state`` indica hasta dónde se calibró, cerrando el riesgo de aplicar InvOLS dos
veces o de ajustar sin calibrar.

Todo es inmutable, como el resto de ``core/models``. Un ``ForceVolume`` NO mantiene
las curvas en RAM (un force-map puede pesar GB): guarda un ``loader`` picklable que
lee la curva N bajo demanda.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

#: Estado de calibración de un segmento.
#:  ``"raw_v"``        señal cruda (V), sin calibrar.
#:  ``"deflection_m"`` deflexión en metros (InvOLS aplicado).
#:  ``"force_n"``      fuerza en newtons (k aplicado); lista para ajustar.
CalState = Literal["raw_v", "deflection_m", "force_n"]

#: Tipo de segmento de una curva de fuerza.
SegmentType = Literal["extend", "retract", "pause", "modulation"]


@dataclass(frozen=True)
class Calibration:
    """Calibración del cantiléver: sensibilidad de deflexión y constante de resorte.

    Attributes:
        invols: Sensibilidad óptica inversa (m/V): deflexión = señal · invols.
        spring_constant: Constante de resorte k (N/m): fuerza = deflexión · k.
        method: Cómo se obtuvo k (``"thermal"``/``"sader"``/``"contact"``/``"manual"``).
        temperature: Temperatura de calibración (K).
        provenance: Metadatos de trazabilidad (fuente de los valores, fecha, etc.).
    """

    invols: float
    spring_constant: float
    method: str = "manual"
    temperature: float = 293.15
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ForceSegment:
    """Un tramo de una curva de fuerza (approach, retract, pausa o modulación).

    Guarda los canales crudos (``raw_height``, ``raw_deflection``) y los derivados
    que va rellenando el pipeline. Ninguna operación salvo ``calibrate`` avanza el
    ``state``; el resto valida lo que necesita con ``require_*``.
    """

    segment_type: SegmentType
    direction: str  # "approach" | "retract" | "static"
    raw_height: np.ndarray  # altura del piezo/medida (m)
    raw_deflection: np.ndarray  # señal cruda (V) — o m si el archivo ya viene calibrado
    time: np.ndarray | None = None  # tiempo (s): loading rate, viscoelasticidad
    cycle: int = 0  # índice de ciclo (curvas multi-ciclo)
    state: CalState = "raw_v"
    # Derivados (None hasta que la operación correspondiente los rellena):
    deflection: np.ndarray | None = None  # m, tras InvOLS
    force: np.ndarray | None = None  # N, tras k
    separation: np.ndarray | None = None  # m, tras height − deflexión
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return int(np.asarray(self.raw_height).size)

    def require_force(self) -> np.ndarray:
        """Fuerza calibrada (N) o error controlado si aún no se calibró."""
        if self.force is None:
            raise ValueError(
                f"Segmento sin fuerza calibrada (state={self.state!r}); "
                "corre la operación 'calibrate' antes de ajustar elasticidad."
            )
        return self.force

    def require_separation(self) -> np.ndarray:
        """Separación punta-muestra (m) o error controlado si no se calculó."""
        if self.separation is None:
            raise ValueError(
                "Segmento sin separación punta-muestra; corre 'tip_sample_separation' "
                f"(state actual={self.state!r})."
            )
        return self.separation


@dataclass(frozen=True)
class ForceCurve:
    """Una curva de fuerza completa: uno o más segmentos, calibración y posición.

    Reemplaza al ``ForceCurve`` plano de ``mechanics`` a futuro; por ahora convive con
    él. Expone ``z``/``force`` (del segmento extend) como *shim* de compatibilidad.
    """

    segments: tuple[ForceSegment, ...]
    calibration: Calibration | None = None
    position: tuple[float, float] | None = None  # (x, y) en m, para force-maps
    index: int = 0
    metadata: dict = field(default_factory=dict)

    def segment(self, kind: SegmentType, cycle: int = 0) -> ForceSegment | None:
        """Primer segmento de tipo ``kind`` (y ciclo ``cycle``), o ``None``."""
        for s in self.segments:
            if s.segment_type == kind and s.cycle == cycle:
                return s
        return None

    @property
    def extend(self) -> ForceSegment | None:
        return self.segment("extend")

    @property
    def retract(self) -> ForceSegment | None:
        return self.segment("retract")

    def _primary(self) -> ForceSegment:
        seg = self.extend or (self.segments[0] if self.segments else None)
        if seg is None:
            raise ValueError("La curva no tiene segmentos.")
        return seg

    # --- shim de compatibilidad con el ForceCurve plano (z / force) ---
    @property
    def z(self) -> np.ndarray:
        """Altura del segmento extend (compatibilidad con el modelo antiguo)."""
        return self._primary().raw_height

    @property
    def force(self) -> np.ndarray | None:
        """Fuerza del segmento extend, si está calibrada (compatibilidad)."""
        return self._primary().force


@dataclass(frozen=True)
class InMemoryLoader:
    """Loader picklable para curvas ya en memoria (p. ej. ``.nid``, curvas chicas).

    Es una clase (no un ``lambda``/closure) para que ``pickle`` la pueda enviar a
    procesos worker: ``ProcessPoolExecutor`` serializa el loader, y las funciones
    anónimas no son serializables. Un dataclass congelado es picklable por defecto.
    Los lectores de archivos grandes usarán en su lugar un loader que guarde solo la
    ruta y abra su propio handle por worker.
    """

    curves: tuple[ForceCurve, ...]

    def __call__(self, index: int) -> ForceCurve:
        return self.curves[index]

    def __len__(self) -> int:
        return len(self.curves)


@dataclass(frozen=True)
class ForceVolume:
    """Grilla de curvas de fuerza (force-map / QI) con carga perezosa.

    No mantiene las curvas en RAM: ``loader(index)`` las lee bajo demanda. El
    ``loader`` debe ser **picklable** (ver :class:`InMemoryLoader`) para poder correr
    el pipeline en paralelo con ``ProcessPoolExecutor``.
    """

    loader: Callable[[int], ForceCurve]
    n_curves: int
    grid_shape: tuple[int, int]  # (rows, cols)
    x_range: float  # m
    y_range: float  # m
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return self.n_curves

    def curve(self, index: int) -> ForceCurve:
        """Lee la curva ``index`` (bajo demanda vía el loader)."""
        if not 0 <= index < self.n_curves:
            raise IndexError(f"curva {index} fuera de rango (0..{self.n_curves - 1})")
        return self.loader(index)

    @classmethod
    def from_curves(
        cls,
        curves: tuple[ForceCurve, ...] | list[ForceCurve],
        grid_shape: tuple[int, int],
        x_range: float,
        y_range: float,
        metadata: dict | None = None,
    ) -> ForceVolume:
        """Construye un volumen desde curvas en memoria (loader in-memory picklable)."""
        curves = tuple(curves)
        return cls(
            loader=InMemoryLoader(curves),
            n_curves=len(curves),
            grid_shape=grid_shape,
            x_range=x_range,
            y_range=y_range,
            metadata=metadata or {},
        )

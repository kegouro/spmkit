"""Modelos de datos del dominio SPM.

Estas estructuras son el contrato público entre el `core` y las capas
superiores (CLI / GUI). Son inmutables y no dependen de ninguna librería
de interfaz.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class SPMChannel:
    """Un canal 2D de un barrido SPM (p.ej. topografía, amplitud, CPD).

    Los datos están siempre en unidades físicas (no en cuentas del ADC).

    Attributes:
        name: Nombre del canal (p.ej. ``"Z-Axis"``, ``"CPD"``).
        data: Matriz 2D ``(lines, points)`` en unidades físicas.
        unit: Unidad física de ``data`` (p.ej. ``"m"``, ``"V"``).
        x_range: Tamaño físico del eje rápido (X) en metros.
        y_range: Tamaño físico del eje lento (Y) en metros.
        direction: ``"forward"`` o ``"backward"``.
        group: Nombre del grupo de origen (p.ej. ``"Scan forward"``).
        metadata: Metadatos crudos del canal.
    """

    name: str
    data: np.ndarray
    unit: str
    x_range: float
    y_range: float
    direction: str = "forward"
    group: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        """Forma ``(lines, points)`` del canal."""
        rows, cols = self.data.shape
        return int(rows), int(cols)

    @property
    def pixel_size_x(self) -> float:
        """Tamaño de píxel en X (metros/píxel)."""
        return self.x_range / self.data.shape[1]

    @property
    def pixel_size_y(self) -> float:
        """Tamaño de píxel en Y (metros/píxel)."""
        return self.y_range / self.data.shape[0]

    def with_data(self, data: np.ndarray) -> SPMChannel:
        """Devuelve una copia del canal con nuevos datos (mismo eje/unidad)."""
        return SPMChannel(
            name=self.name,
            data=data,
            unit=self.unit,
            x_range=self.x_range,
            y_range=self.y_range,
            direction=self.direction,
            group=self.group,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class SPMData:
    """Un archivo SPM completo: varios canales más metadatos del barrido."""

    channels: tuple[SPMChannel, ...]
    metadata: dict = field(default_factory=dict)
    source_path: str = ""

    @property
    def names(self) -> list[str]:
        """Nombres de todos los canales presentes."""
        return [c.name for c in self.channels]

    def get(self, name: str, direction: str = "forward") -> SPMChannel:
        """Devuelve el canal ``name`` en la dirección indicada.

        Si no existe esa dirección, devuelve el primer canal que coincida
        por nombre. Lanza ``KeyError`` si no hay ninguno.
        """
        for ch in self.channels:
            if ch.name == name and ch.direction == direction:
                return ch
        for ch in self.channels:
            if ch.name == name:
                return ch
        raise KeyError(f"Canal no encontrado: {name!r}. Disponibles: {self.names}")

    def __getitem__(self, name: str) -> SPMChannel:
        return self.get(name)

    def __iter__(self) -> Iterator[SPMChannel]:
        return iter(self.channels)

    def __len__(self) -> int:
        return len(self.channels)

"""Perfiles de línea sobre imágenes SPM.

Extrae el perfil de altura a lo largo de un segmento arbitrario usando
interpolación bilineal, devolviendo distancia física vs altura.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spmkit.core.models import SPMChannel


@dataclass(frozen=True)
class Profile:
    """Perfil de línea: distancia (m) vs altura (unidad del canal)."""

    distance: np.ndarray
    height: np.ndarray
    unit: str
    distance_unit: str = "m"

    def __len__(self) -> int:
        return int(self.distance.size)


def _bilinear(z: np.ndarray, r: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Muestreo bilineal de ``z`` en coordenadas fraccionarias (fila, col)."""
    rows, cols = z.shape
    r0 = np.clip(np.floor(r).astype(int), 0, rows - 1)
    c0 = np.clip(np.floor(c).astype(int), 0, cols - 1)
    r1 = np.clip(r0 + 1, 0, rows - 1)
    c1 = np.clip(c0 + 1, 0, cols - 1)
    dr = r - r0
    dc = c - c0
    top = z[r0, c0] * (1 - dc) + z[r0, c1] * dc
    bot = z[r1, c0] * (1 - dc) + z[r1, c1] * dc
    return top * (1 - dr) + bot * dr


def line(
    channel: SPMChannel,
    p0: tuple[float, float],
    p1: tuple[float, float],
    n: int | None = None,
) -> Profile:
    """Extrae un perfil entre dos puntos en **coordenadas de píxel** ``(col, row)``.

    Args:
        channel: Canal de origen.
        p0: Punto inicial ``(col, row)`` en píxeles.
        p1: Punto final ``(col, row)`` en píxeles.
        n: Número de muestras. Por defecto, la longitud del segmento en píxeles.

    Returns:
        Un :class:`Profile` con distancia física acumulada y altura.
    """
    z = np.asarray(channel.data, dtype=np.float64)
    if z.ndim != 2 or not channel.is_spatial:
        raise ValueError("El perfil requiere un canal de imagen espacial 2D")
    (x0, y0), (x1, y1) = p0, p1
    rows_count, cols_count = z.shape
    endpoints = (x0, y0, x1, y1)
    if not all(np.isfinite(value) for value in endpoints) or not (
        0 <= x0 <= cols_count - 1
        and 0 <= x1 <= cols_count - 1
        and 0 <= y0 <= rows_count - 1
        and 0 <= y1 <= rows_count - 1
    ):
        raise ValueError("Punto fuera de los límites de la imagen")
    seg_px = float(np.hypot(x1 - x0, y1 - y0))
    if n is None:
        n = max(2, int(round(seg_px)) + 1)
    elif n < 1:
        raise ValueError("n debe ser >= 1")

    cols = np.linspace(x0, x1, n)
    rows = np.linspace(y0, y1, n)
    height = _bilinear(z, rows, cols)

    # Distancia física: escala media de píxel ponderada por la dirección.
    dx = (x1 - x0) * channel.pixel_size_x
    dy = (y1 - y0) * channel.pixel_size_y
    total = float(np.hypot(dx, dy))
    distance = np.linspace(0.0, total, n)

    return Profile(distance=distance, height=height, unit=channel.unit)

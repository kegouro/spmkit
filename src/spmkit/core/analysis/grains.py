"""Detección de granos/partículas y estadística de tamaños sobre imágenes de topografía SPM.

Las funciones esperan datos **ya nivelados** (ver :mod:`spmkit.core.analysis.leveling`).

El algoritmo de segmentación usa un umbral de altura para binarizar la imagen y luego
etiqueta componentes conexos con ``scipy.ndimage.label``. Si ``scipy`` no está
disponible, se lanza un ``ImportError`` con instrucciones de instalación.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from spmkit.core.models import SPMChannel


@dataclass(frozen=True)
class GrainResult:
    """Resultado de la detección de granos sobre un canal de topografía.

    Attributes:
        n_grains: Número de granos detectados.
        labels: Mapa de etiquetas 2D (0 = fondo, 1..n_grains = grano i).
        areas: Área de cada grano en m² (array de longitud ``n_grains``).
        equivalent_diameters: Diámetro del círculo de igual área, en m.
        mean_height: Altura media de cada grano (misma unidad que el canal).
        coverage: Fracción del área total cubierta por granos (0..1).
        unit_length: Unidad de las magnitudes de longitud/altura (por defecto ``"m"``).
    """

    n_grains: int
    labels: np.ndarray
    areas: np.ndarray
    equivalent_diameters: np.ndarray
    mean_height: np.ndarray
    coverage: float
    unit_length: str = "m"

    # campo auxiliar para la firma de dataclass frozen; no se incluye en to_dict
    _pixel_area: float = field(default=0.0, compare=False)

    def to_dict(self) -> dict:
        """Devuelve un diccionario serializable (arrays → listas)."""
        return {
            "n_grains": self.n_grains,
            "areas": self.areas.tolist(),
            "equivalent_diameters": self.equivalent_diameters.tolist(),
            "mean_height": self.mean_height.tolist(),
            "coverage": self.coverage,
            "unit_length": self.unit_length,
            "mean_diameter": self.mean_diameter,
            "density_per_um2": self.density,
        }

    @property
    def mean_diameter(self) -> float:
        """Diámetro equivalente promedio en metros (0 si no hay granos)."""
        if self.n_grains == 0:
            return 0.0
        return float(np.mean(self.equivalent_diameters))

    @property
    def density(self) -> float:
        """Densidad de granos en granos/µm² (0 si no hay granos o área nula)."""
        if self.n_grains == 0 or self._pixel_area == 0.0:
            return 0.0
        total_area_um2 = self.labels.size * self._pixel_area * 1e12  # m² → µm²
        return self.n_grains / total_area_um2


def detect(
    channel: SPMChannel,
    threshold: float | None = None,
    min_size: int = 4,
    relative_height: float = 0.5,
) -> GrainResult:
    """Detecta granos/partículas en un canal de topografía SPM.

    El canal debe estar **ya nivelado** (plano de fondo restado). El algoritmo:

    1. Calcula un umbral de altura si no se proporciona uno explícito.
       Umbral automático: ``mean(z) + relative_height * (max(z) - mean(z))``.
       Esto marca los píxeles que superan una fracción ``relative_height`` del
       rango entre la media y el máximo, lo que es intuitivo para topografías
       con partículas sobre fondo plano.
    2. Binariza la imagen: máscara = ``data > threshold``.
    3. Etiqueta componentes conexos con ``scipy.ndimage.label`` (conectividad 8).
    4. Descarta granos con menos de ``min_size`` píxeles.
    5. Calcula estadísticas por grano.

    Args:
        channel: Canal 2D de topografía (unidades físicas, ya nivelado).
        threshold: Umbral de altura en las mismas unidades que ``channel.data``.
            Si es ``None``, se calcula automáticamente (ver descripción).
        min_size: Tamaño mínimo de grano en píxeles. Granos más pequeños se
            descartan (filtro de ruido / artefactos).
        relative_height: Fracción para el umbral automático. Solo se usa cuando
            ``threshold`` es ``None``. Debe estar en (0, 1].

    Returns:
        :class:`GrainResult` con estadísticas de todos los granos detectados.

    Raises:
        ImportError: Si ``scipy`` no está instalado.
        ValueError: Si ``relative_height`` está fuera del rango (0, 1].
    """
    try:
        from scipy.ndimage import label as ndlabel
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "La detección de granos requiere scipy. " "Instala con: pip install 'spmkit[grains]'"
        ) from exc

    if not (0.0 < relative_height <= 1.0):
        raise ValueError(f"relative_height debe estar en (0, 1]; se recibió {relative_height!r}")

    z = np.asarray(channel.data, dtype=np.float64)
    pixel_area = channel.pixel_size_x * channel.pixel_size_y  # m²/píxel

    # --- Umbral automático ---------------------------------------------------
    if threshold is None:
        z_mean = float(np.nanmean(z))
        z_max = float(np.nanmax(z))
        threshold = z_mean + relative_height * (z_max - z_mean)

    # --- Segmentación -------------------------------------------------------
    mask = z > threshold

    # Estructura de conectividad 8 (incluye diagonales)
    structure = np.ones((3, 3), dtype=int)
    labeled_array, n_found = ndlabel(mask, structure=structure)

    # --- Filtrado por tamaño mínimo ----------------------------------------
    # Reindexamos los granos supervivientes para que las etiquetas sean
    # contiguas desde 1 hasta n_grains.
    new_labels = np.zeros_like(labeled_array)
    valid_ids: list[int] = []
    new_id = 0
    for orig_id in range(1, n_found + 1):
        grain_mask = labeled_array == orig_id
        if int(grain_mask.sum()) >= min_size:
            new_id += 1
            new_labels[grain_mask] = new_id
            valid_ids.append(orig_id)

    n_grains = new_id

    # --- Estadísticas por grano --------------------------------------------
    areas = np.zeros(n_grains, dtype=np.float64)
    equivalent_diameters = np.zeros(n_grains, dtype=np.float64)
    mean_height = np.zeros(n_grains, dtype=np.float64)

    for idx, _orig_id in enumerate(valid_ids):
        grain_mask = new_labels == (idx + 1)
        n_pixels = int(grain_mask.sum())
        area = n_pixels * pixel_area
        areas[idx] = area
        equivalent_diameters[idx] = 2.0 * math.sqrt(area / math.pi)
        mean_height[idx] = float(np.mean(z[grain_mask]))

    total_pixels = new_labels.size
    covered_pixels = int((new_labels > 0).sum())
    coverage = covered_pixels / total_pixels if total_pixels > 0 else 0.0

    return GrainResult(
        n_grains=n_grains,
        labels=new_labels,
        areas=areas,
        equivalent_diameters=equivalent_diameters,
        mean_height=mean_height,
        coverage=coverage,
        unit_length=channel.unit,
        _pixel_area=pixel_area,
    )

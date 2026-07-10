"""Encuadre y límites de pan compartidos por los visores basados en ``pg.ImageView``.

Tres perspectivas dibujan imágenes con el mismo widget (Imagen, Granos, Mapa). Sin
``setLimits`` el ViewBox se desplaza al infinito; sin un ``autoRange`` explícito la imagen
queda mal encuadrada si el ``setImage`` corrió con el panel oculto (viewport de tamaño 0).
Este helper unifica ambos arreglos en un solo lugar.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def fit_image_view(view: Any, data: Any, padding: float = 0.02) -> None:
    """Reencuadra ``view`` (el ViewBox de ``ImageView.getView()``) sobre ``data`` y acota
    el pan/zoom a su extent (± margen), evitando el desplazamiento infinito."""
    arr = np.asarray(data)
    rows, cols = (arr.shape[0], 1) if arr.ndim == 1 else arr.shape[:2]
    view.setLimits(
        xMin=-0.1 * cols,
        xMax=1.1 * cols,
        yMin=-0.1 * rows,
        yMax=1.1 * rows,
        maxXRange=1.4 * cols,
        maxYRange=1.4 * rows,
    )
    view.autoRange(padding=padding)

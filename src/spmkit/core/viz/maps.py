"""Figuras de mapas de propiedades de force-volume (módulo, adhesión, disipación).

Renderiza los mapas 2D de un :class:`~spmkit.core.analysis.forcevolume.VolumeResult`
a un PNG de presentación con colorbars y colormap perceptual, listo para mostrar a
labs/universidades. matplotlib se importa de forma perezosa (extra ``viz``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spmkit.core.viz import colormaps

#: Etiqueta y factor de escala de presentación por propiedad de force-volume.
_MAP_LABELS = {
    "young_modulus": ("Módulo (kPa)", 1e-3),
    "adhesion": ("Adhesión (nN)", 1e9),
    "dissipation": ("Disipación (fJ)", 1e15),
    "r_squared": ("R²", 1.0),
    "contact_point": ("Contacto (nm)", 1e9),
}


def save_property_maps(
    maps: dict[str, Any],
    path: str | Path,
    keys: list[str] | None = None,
    title: str = "",
    colormap: str = "batlow",
    dpi: int = 300,
    extent: tuple[float, float, float, float] | None = None,
) -> Path:
    """Renderiza mapas de propiedades de force-volume a una figura PNG con colorbars.

    ``maps`` es el dict ``nombre -> arreglo 2D`` de ``VolumeResult.maps``. Solo grafica
    las claves con etiqueta conocida (módulo, adhesión, disipación, R², contacto) que
    tengan algún valor finito, salvo que se pasen ``keys`` explícitas.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    import numpy as np

    cmap = colormaps.get_cmap(colormap)
    keys = keys or [k for k in maps if k in _MAP_LABELS and np.isfinite(maps[k]).any()]
    if not keys:
        raise ValueError("No hay mapas graficables (todas las propiedades son NaN).")

    fig, axes = plt.subplots(1, len(keys), figsize=(4 * len(keys), 3.8), squeeze=False)
    for ax, key in zip(axes[0], keys, strict=True):
        label, scale = _MAP_LABELS.get(key, (key, 1.0))
        im = ax.imshow(np.asarray(maps[key]) * scale, origin="lower", cmap=cmap, extent=extent)
        ax.set_title(label)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    out = Path(path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out

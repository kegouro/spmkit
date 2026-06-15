"""Colormaps científicos para imágenes SPM.

Combina los colormaps perceptualmente uniformes de Fabio Crameri
(``cmcrameri``, si está instalado) con los de matplotlib, y añade alias
familiares para usuarios de NanoSurf/Gwyddion.
"""

from __future__ import annotations

from typing import Any

#: Colormaps recomendados para topografía/medidas, en orden sugerido.
RECOMMENDED = (
    "batlow",  # Crameri, perceptualmente uniforme (default científico)
    "viridis",
    "inferno",
    "cividis",
    "afmhot",  # clásico AFM
    "gray",
    "bamako",
    "lajolla",
)

#: Alias hacia nombres reales de colormap.
_ALIASES = {
    "nanosurf": "afmhot",
    "gold": "afmhot",
    "topography": "batlow",
}


def available() -> list[str]:
    """Lista de colormaps disponibles (recomendados primero)."""
    names = list(RECOMMENDED)
    try:
        import matplotlib.pyplot as plt

        for name in sorted(plt.colormaps()):
            if name not in names:
                names.append(name)
    except ImportError:  # pragma: no cover - viz opcional
        pass
    return names


def get_cmap(name: str) -> Any:
    """Resuelve un colormap por nombre (Crameri → matplotlib → alias)."""
    name = _ALIASES.get(name, name)
    try:
        from cmcrameri import cm as cmc

        if hasattr(cmc, name):
            return getattr(cmc, name)
    except ImportError:  # pragma: no cover - cmcrameri opcional
        pass
    import matplotlib.pyplot as plt

    try:
        return plt.get_cmap(name)
    except (ValueError, KeyError):
        return plt.get_cmap("viridis")

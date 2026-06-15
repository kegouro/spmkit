"""Colormaps científicos para imágenes SPM.

Combina los colormaps perceptualmente uniformes de Fabio Crameri
(``cmcrameri``, si está instalado) con los de matplotlib, y añade alias
familiares para usuarios de NanoSurf/Gwyddion.
"""

from __future__ import annotations

from typing import Any

#: Colormaps recomendados para topografía/medidas, en orden sugerido.
RECOMMENDED = (
    "gold",  # estilo NanoSurf/Gwyddion (default, familiar para el lab)
    "batlow",  # Crameri, perceptualmente uniforme
    "viridis",
    "inferno",
    "afmhot",
    "cividis",
    "gray",
    "bamako",
)

#: Puntos de control del colormap "gold" estilo NanoSurf (negro→oro→blanco).
_GOLD_STOPS = [
    (0.00, "#000000"),
    (0.25, "#3a1c00"),
    (0.50, "#a85a00"),
    (0.75, "#f0a830"),
    (0.92, "#ffe89a"),
    (1.00, "#ffffff"),
]

#: Alias hacia nombres reales de colormap.
_ALIASES = {
    "nanosurf": "gold",
    "topography": "gold",
}


def _gold_cmap() -> Any:
    """Colormap dorado estilo NanoSurf (cacheado)."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("gold", _GOLD_STOPS)


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
    """Resuelve un colormap por nombre (gold → Crameri → matplotlib → alias)."""
    name = _ALIASES.get(name, name)
    if name == "gold":
        return _gold_cmap()
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


def pyqtgraph_cmap(name: str) -> Any:
    """Devuelve un ``pyqtgraph.ColorMap`` equivalente (para el visor)."""
    import numpy as np
    import pyqtgraph as pg
    from matplotlib.colors import to_rgba

    resolved = _ALIASES.get(name, name)
    if resolved == "gold":
        pos = np.array([s[0] for s in _GOLD_STOPS])
        cols = np.array([[int(c * 255) for c in to_rgba(s[1])] for s in _GOLD_STOPS])
        return pg.ColorMap(pos, cols)
    # Para otros: muestrea el colormap de matplotlib en 256 niveles.
    mpl = get_cmap(resolved)
    pos = np.linspace(0.0, 1.0, 256)
    cols = (np.array([mpl(x) for x in pos]) * 255).astype(int)
    return pg.ColorMap(pos, cols)

"""Colormaps de pyqtgraph para los visores — capa GUI.

Convierte los **datos de color puros** de :mod:`spmkit.core.viz.colormaps` (los stops del
gold NanoSurf, los cmaps de matplotlib) a ``pyqtgraph.ColorMap``. Vive aquí, no en
``core``, porque importa ``pyqtgraph``: el core se mantiene sin toolkits de UI (lo hace
cumplir ``tests/test_architecture.py``).
"""

from __future__ import annotations

from typing import Any


def pyqtgraph_cmap(name: str) -> Any:
    """``pyqtgraph.ColorMap`` equivalente al colormap ``name`` (gold o matplotlib)."""
    import numpy as np
    import pyqtgraph as pg
    from matplotlib.colors import to_rgba

    from spmkit.core.viz.colormaps import _ALIASES, _GOLD_STOPS, get_cmap

    resolved = _ALIASES.get(name, name)
    if resolved == "gold":
        pos = np.array([s[0] for s in _GOLD_STOPS])
        cols = np.array([[int(c * 255) for c in to_rgba(s[1])] for s in _GOLD_STOPS])
        return pg.ColorMap(pos, cols)
    mpl = get_cmap(resolved)
    pos = np.linspace(0.0, 1.0, 256)
    cols = (np.array([mpl(x) for x in pos]) * 255).astype(int)
    return pg.ColorMap(pos, cols)

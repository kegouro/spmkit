"""Dispatcher de curvas de fuerza por extensión → siempre un ``ForceVolume``.

La GUI y el batch quieren un único punto de entrada: dales una ruta y devuelve un
``ForceVolume`` sin importar el formato. Las curvas sueltas (JPK ``.jpk-force``) se
envuelven en un volumen 1×1; los force-maps (``.nid``) se leen perezosos tal cual.
"""

from __future__ import annotations

from pathlib import Path

from spmkit.core.io.jpk import load_jpk_force
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceCurve, ForceVolume


def _wrap_curve(curve: ForceCurve) -> ForceVolume:
    """Envuelve una curva suelta en un volumen 1×1 (para la vista unificada)."""
    return ForceVolume.from_curves((curve,), grid_shape=(1, 1), x_range=0.0, y_range=0.0)


#: Extensión → lector. Cada lector devuelve un ``ForceVolume``.
_LOADERS = {
    ".nid": load_nid_force,
    ".jpk-force": lambda p: _wrap_curve(load_jpk_force(p)),
    ".jpk": lambda p: _wrap_curve(load_jpk_force(p)),
}


def supported_force_extensions() -> tuple[str, ...]:
    """Extensiones de curva de fuerza que ``load_force`` sabe leer."""
    return tuple(sorted(_LOADERS))


def load_force(path: str | Path) -> ForceVolume:
    """Lee una curva/volumen de fuerza desde ``path`` según su extensión.

    Raises:
        ValueError: si la extensión no está soportada.
    """
    p = Path(path)
    ext = p.suffix.lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        raise ValueError(
            f"Extensión de curva de fuerza no soportada: {ext!r}. "
            f"Soportadas: {', '.join(supported_force_extensions())}"
        )
    return loader(p)

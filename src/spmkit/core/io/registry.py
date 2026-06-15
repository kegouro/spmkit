"""Registro de parsers: despacha ``load()`` según la extensión del archivo."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from spmkit.core.io.nhf import load_nhf
from spmkit.core.io.nid import load_nid
from spmkit.core.models import SPMData

_PARSERS: dict[str, Callable[[str | Path], SPMData]] = {
    ".nid": load_nid,
    ".nhf": load_nhf,
}


def supported_extensions() -> list[str]:
    """Extensiones de archivo soportadas."""
    return sorted(_PARSERS)


def load(path: str | Path) -> SPMData:
    """Carga un archivo SPM autodetectando el formato por extensión.

    Args:
        path: Ruta al archivo (``.nid`` o ``.nhf``).

    Returns:
        Un :class:`SPMData` con todos los canales del archivo.

    Raises:
        ValueError: Si la extensión no está soportada.
    """
    path = Path(path)
    parser = _PARSERS.get(path.suffix.lower())
    if parser is None:
        raise ValueError(
            f"Formato no soportado: {path.suffix!r}. "
            f"Soportados: {', '.join(supported_extensions())}"
        )
    return parser(path)

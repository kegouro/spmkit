"""Interop con Gwyddion: lectura y escritura del formato ``.gwy``.

Usa la librería pura-Python ``gwyfile`` (no requiere tener Gwyddion
instalado), de modo que los archivos viajan sin fricción entre spmkit y el
flujo de trabajo del lab en Gwyddion.

Necesita el extra ``gwy`` (``pip install 'spmkit[gwy]'``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from spmkit.core.models import SPMChannel, SPMData

_DIRECTIONS = ("forward", "backward")


def _import_gwyfile():  # type: ignore[no-untyped-def]
    try:
        import gwyfile
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "La interop .gwy requiere gwyfile. Instala con: pip install 'spmkit[gwy]'"
        ) from exc
    return gwyfile


def _split_direction(title: str) -> tuple[str, str]:
    """Separa ``'Z-Axis forward'`` → ``('Z-Axis', 'forward')``."""
    for direction in _DIRECTIONS:
        if title.endswith(direction):
            return title[: -len(direction)].strip(), direction
    return title, "forward"


def load_gwy(path: str | Path) -> SPMData:
    """Lee un archivo Gwyddion ``.gwy`` y devuelve un :class:`SPMData`."""
    gwyfile = _import_gwyfile()
    from gwyfile.util import get_datafields

    path = Path(path)
    try:
        container = gwyfile.load(str(path))
    except (AssertionError, ValueError, OSError, EOFError) as exc:
        # gwyfile valida el magic number con un `assert` pelado; ante un archivo inválido
        # o corrupto damos un error claro en vez de filtrar un AssertionError sin mensaje.
        raise ValueError(f"archivo .gwy inválido o corrupto: {path.name}") from exc
    datafields = get_datafields(container)

    channels: list[SPMChannel] = []
    for title, df in datafields.items():
        name, direction = _split_direction(title)
        unit = getattr(getattr(df, "si_unit_z", None), "unitstr", "") or ""
        channels.append(
            SPMChannel(
                name=name,
                data=np.asarray(df.data, dtype=np.float64),
                unit=unit,
                x_range=float(df.xreal),
                y_range=float(df.yreal),
                direction=direction,
                group=title,
                metadata={"gwy_title": title},
            )
        )
    if not channels:
        raise ValueError(f"No se encontraron canales en el .gwy: {path}")
    return SPMData(channels=tuple(channels), metadata={"format": "gwy"}, source_path=str(path))


def save_gwy(data: SPMData, path: str | Path) -> Path:
    """Escribe un :class:`SPMData` a ``.gwy`` (abrible directamente en Gwyddion)."""
    _import_gwyfile()
    from gwyfile.objects import GwyContainer, GwyDataField, GwySIUnit

    path = Path(path)
    container = GwyContainer()
    seen: dict[str, int] = {}
    for i, ch in enumerate(data.channels):
        df = GwyDataField(
            np.ascontiguousarray(ch.data, dtype=np.float64),
            xreal=ch.x_range or 1.0,
            yreal=ch.y_range or 1.0,
            si_unit_xy=GwySIUnit(unitstr="m"),
            si_unit_z=GwySIUnit(unitstr=ch.unit or ""),
        )
        container[f"/{i}/data"] = df
        container[f"/{i}/data/title"] = _unique_title(f"{ch.name} {ch.direction}".strip(), seen)
    container.tofile(str(path))
    return path


def _unique_title(title: str, seen: dict[str, int]) -> str:
    """Garantiza títulos únicos (Gwyddion colapsa títulos repetidos)."""
    if title not in seen:
        seen[title] = 1
        return title
    seen[title] += 1
    return f"{title} ({seen[title]})"

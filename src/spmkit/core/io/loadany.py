"""Dispatch unificado de carga por capacidades — ``inspect_any`` / ``load_any``.

Fuente única para abrir cualquier formato registrado: primero **inspecciona** (barato,
solo cabecera) para saber qué contiene el archivo, luego **carga** el ``kind`` pedido.
La GUI usa ``inspect_any`` para ofrecer "abrir como Imagen / como Mapa de curvas" cuando
un archivo declara varios ``kinds`` (p. ej. un QI).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spmkit.core.plugins.contracts import DatasetInfo, Kind
from spmkit.core.plugins.registry import reader_for, supported_extensions


def inspect_any(path: str | Path) -> DatasetInfo:
    """Metadatos de ``path`` sin cargar los datos pesados.

    Raises:
        ValueError: si ninguna extensión registrada maneja el archivo.
    """
    reader = reader_for(path)
    if reader is None:
        raise ValueError(
            f"Formato no soportado: {Path(path).suffix!r}. "
            f"Soportados: {', '.join(supported_extensions())}"
        )
    return reader.inspect(path)


def load_any(path: str | Path, kind: Kind | None = None) -> tuple[Any, Kind]:
    """Carga ``path`` como el ``kind`` pedido (o el primero declarado).

    Returns:
        ``(dato, kind)`` — ``SPMData`` si ``kind == "image"``, ``ForceVolume`` si
        ``"force"``.

    Raises:
        ValueError: si el formato no está soportado o el ``kind`` pedido no está en el
            archivo.
    """
    info = inspect_any(path)
    chosen: Kind = kind or info.kinds[0]
    if chosen not in info.kinds:
        raise ValueError(
            f"{Path(path).name} no contiene datos de tipo {chosen!r}; tiene {info.kinds}."
        )
    reader = reader_for(path)
    assert reader is not None  # inspect_any ya lo garantizó
    return reader.load(path, chosen), chosen

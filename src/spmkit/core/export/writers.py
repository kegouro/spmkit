"""Exportación de datos y resultados procesados a formatos abiertos.

Soporta CSV y JSON (siempre disponibles) y HDF5 (requiere el extra
``hdf5``). Las funciones aceptan tanto los dataclasses de resultados
(``RoughnessResult``, ``CPDResult``, ``Profile``) como objetos
:class:`SPMData` completos.
"""

from __future__ import annotations

import csv as _csv
import json as _json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.analysis.profiles import Profile
from spmkit.core.models import SPMData


def _to_serializable(obj: Any) -> Any:
    """Convierte dataclasses / ndarrays a tipos JSON-serializables."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


def to_json(result: Any, path: str | Path) -> Path:
    """Escribe cualquier resultado (dataclass/dict) a JSON."""
    path = Path(path)
    path.write_text(
        _json.dumps(_to_serializable(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def to_csv(result: Any, path: str | Path) -> Path:
    """Escribe un resultado a CSV.

    * Para :class:`Profile`: dos columnas ``distance,height``.
    * Para :class:`VolumeResult` (mapa de fuerza): informe científico
      (cabecera de metadatos + estadística por propiedad + tabla por punto con unidades),
      vía :func:`export_volume`.
    * Para dataclasses escalares (rugosidad, CPD): formato ``key,value``.
    """
    from spmkit.core.analysis.forcevolume import VolumeResult

    if isinstance(result, VolumeResult):
        return export_volume(result, path)

    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.writer(fh)
        if isinstance(result, Profile):
            writer.writerow([f"distance[{result.distance_unit}]", f"height[{result.unit}]"])
            for d, h in zip(result.distance, result.height, strict=True):
                writer.writerow([d, h])
        elif is_dataclass(result) and not isinstance(result, type):
            writer.writerow(["key", "value"])
            for key, value in asdict(result).items():
                writer.writerow([key, value])
        else:
            raise TypeError(f"No sé exportar a CSV: {type(result).__name__}")
    return path


def export_volume(
    result: Any,
    path: str | Path,
    source: str = "",
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """Exporta un ``VolumeResult`` (mapa de fuerza) a un CSV científico y trazable.

    El archivo lleva tres bloques: (1) cabecera de metadatos comentada (``#``) con fuente,
    grilla, curvas OK/fallidas y los parámetros de análisis en ``extra_meta``; (2) estadística
    robusta por propiedad **con su unidad**; (3) tabla de **una fila por punto** de la grilla
    con cada propiedad y su unidad en el encabezado. Las propiedades **sin ningún dato válido**
    (p. ej. disipación sin rama de retracción) se **omiten** con una nota, en vez de volcar
    columnas de NaN. Un punto cuyo ajuste falló deja la celda **vacía** (no ``NaN``).
    """
    from spmkit.core.analysis.forcevolume import PROPERTY_UNITS

    path = Path(path)
    rows_n, cols_n = result.grid_shape
    present = [k for k in result.maps if bool(np.isfinite(result.maps[k]).any())]
    omitted = [k for k in result.maps if k not in present]

    def _col(key: str) -> str:
        unit = PROPERTY_UNITS.get(key, "")
        return f"{key} [{unit}]" if unit else key

    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("# spmkit — exportación de mapa de fuerza (force-volume)\n")
        if source:
            fh.write(f"# fuente: {source}\n")
        fh.write(
            f"# grilla: {rows_n} x {cols_n}  ·  curvas OK: {result.n_ok}  ·  "
            f"fallidas: {result.n_failed}\n"
        )
        for key, value in (extra_meta or {}).items():
            fh.write(f"# {key}: {value}\n")
        if omitted:
            fh.write(f"# propiedades sin datos (omitidas): {', '.join(omitted)}\n")

        writer = _csv.writer(fh)
        fh.write("#\n# --- estadística por propiedad ---\n")
        writer.writerow(["propiedad", "unidad", "mediana", "media", "std", "min", "max", "n"])
        for key in present:
            s = result.stats(key)
            writer.writerow(
                [
                    key,
                    PROPERTY_UNITS.get(key, ""),
                    s["median"],
                    s["mean"],
                    s["std"],
                    s["min"],
                    s["max"],
                    s["n"],
                ]
            )

        fh.write("#\n# --- datos por punto ---\n")
        writer.writerow(["row", "col", *[_col(k) for k in present]])
        for r in range(rows_n):
            for c in range(cols_n):
                cells: list[Any] = [r, c]
                for key in present:
                    v = float(result.maps[key][r, c])
                    cells.append("" if not np.isfinite(v) else v)
                writer.writerow(cells)
    return path


def to_hdf5(data: SPMData, path: str | Path) -> Path:
    """Escribe un :class:`SPMData` completo a HDF5 (un dataset por canal)."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "Exportar a HDF5 requiere h5py. Instala con: pip install 'spmkit[hdf5]'"
        ) from exc

    path = Path(path)
    with h5py.File(path, "w") as f:
        f.attrs["source_path"] = data.source_path
        f.attrs["format"] = str(data.metadata.get("format", ""))
        for i, ch in enumerate(data.channels):
            dset = f.create_dataset(f"{ch.group}/{ch.name}_{i}", data=ch.data)
            dset.attrs["name"] = ch.name
            dset.attrs["unit"] = ch.unit
            dset.attrs["x_range"] = ch.x_range
            dset.attrs["y_range"] = ch.y_range
            dset.attrs["direction"] = ch.direction
    return path

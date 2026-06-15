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
    * Para dataclasses escalares (rugosidad, CPD): formato ``key,value``.
    """
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

"""Parser del formato NanoSurf ``.nhf`` (nuevo, basado en HDF5).

El formato ``.nhf`` es un contenedor HDF5. Esta implementación recorre el
árbol HDF5 de forma genérica: cada *dataset* 2D se interpreta como un canal,
tomando unidades/escala de los atributos cuando están disponibles.

.. note::
   Implementación experimental con contrato sintético reproducible, aún no
   validada contra un instrumento u oráculo externo. Necesita el extra
   ``hdf5`` (``pip install spmkit[hdf5]``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.models import SPMChannel, SPMData


def _attr(obj: Any, *keys: str, default: Any = None) -> Any:
    """Devuelve el primer atributo presente entre ``keys``."""
    for key in keys:
        if key in obj.attrs:
            val = obj.attrs[key]
            if isinstance(val, bytes):
                return val.decode("utf-8", "replace")
            return val
    return default


def load_nhf(path: str | Path) -> SPMData:
    """Lee un archivo NanoSurf ``.nhf`` (HDF5) y devuelve un :class:`SPMData`."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "Leer .nhf requiere h5py. Instala con: pip install 'spmkit[hdf5]'"
        ) from exc

    path = Path(path)
    channels: list[SPMChannel] = []

    try:
        with h5py.File(path, "r") as f:

            def visit(name: str, obj: Any) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                if obj.ndim != 2:
                    return
                data = np.asarray(obj[()], dtype=np.float64)
                channels.append(
                    SPMChannel(
                        name=_attr(obj, "name", "Name", default=name.split("/")[-1]),
                        data=data,
                        unit=_attr(obj, "unit", "Unit", "base_unit", default=""),
                        x_range=float(_attr(obj, "x_range", "image_size_x", default=0.0)),
                        y_range=float(_attr(obj, "y_range", "image_size_y", default=0.0)),
                        direction=_attr(obj, "direction", default="forward"),
                        group=name.rsplit("/", 1)[0],
                        metadata={k: _attr(obj, k) for k in obj.attrs},
                    )
                )

            f.visititems(visit)
            root_meta = {k: _attr(f, k) for k in f.attrs}
    except OSError as exc:
        raise ValueError(
            f"No se pudo abrir o leer el .nhf; puede ser inválido, corrupto o inaccesible: {path}"
        ) from exc

    if not channels:
        raise ValueError(f"No se encontraron canales 2D en el .nhf: {path}")

    metadata = {"format": "nhf", "info": root_meta}
    return SPMData(channels=tuple(channels), metadata=metadata, source_path=str(path))

"""Parser para formato .npz proveniente de generadores sintéticos analíticos."""

from pathlib import Path

import numpy as np

from spmkit.core.models import SPMChannel, SPMData


def load_npz(path: str | Path) -> SPMData:
    """Carga un archivo .npz empaquetado (ground truth o corrupción).

    El archivo .npz debe contener:
    - z_data (ndarray 2D)
    - x_size_m (ndarray de tamaño 1 o float escalar)
    - y_size_m (ndarray de tamaño 1 o float escalar)
    - z_unit (ndarray de tamaño 1 o str)
    - model_name (ndarray de tamaño 1 o str, opcional)
    """
    path = Path(path)

    with np.load(path) as data:
        z_data = data["z_data"]

        # Extraer variables con fallback seguro para scalars vs arrays
        x_size = (
            float(data["x_size_m"][0]) if data["x_size_m"].ndim > 0 else float(data["x_size_m"])
        )
        y_size = (
            float(data["y_size_m"][0]) if data["y_size_m"].ndim > 0 else float(data["y_size_m"])
        )
        z_unit = str(data["z_unit"][0]) if data["z_unit"].ndim > 0 else str(data["z_unit"])

        model_name = "Z-Axis"
        if "model_name" in data:
            model_name = (
                str(data["model_name"][0])
                if data["model_name"].ndim > 0
                else str(data["model_name"])
            )
            # SPM-Kit prefiere "Z-Axis" como canal primario para
            # que los comandos por defecto lo encuentren, o bien el model name.
            # Lo forzaremos a "Z-Axis" y pasaremos model_name en metadata.

    # Crear un único canal simulando la topografía
    ch = SPMChannel(
        name="Z-Axis",
        data=z_data,
        unit=z_unit,
        x_range=x_size,
        y_range=y_size,
        direction="forward",
        group="synthetic",
        metadata={"source": "npz", "model_name": model_name},
    )

    return SPMData(channels=(ch,))

"""Backend de cómputo — CPU (NumPy) o GPU (CuPy/CUDA), con detección y fallback.

La ruta rápida de los mapas de force-volume está **vectorizada**: en vez de correr un
ajuste Python por curva, opera sobre toda la grilla de una vez con álgebra de arreglos.
Ese mismo código corre en NumPy (CPU) o en CuPy (GPU CUDA) sin cambios, porque CuPy
replica la API de NumPy. Si no hay GPU compatible, ``gpu`` no aparece y todo usa CPU.

No se implementa física aquí: sólo la elección de "dónde" corren los arreglos.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: Explicación breve para el usuario (pop-up al elegir motor).
CPU_INFO = (
    "CPU (NumPy) — vectorizado sobre todas las curvas a la vez. Rápido y siempre "
    "disponible; ideal hasta decenas de miles de curvas."
)
GPU_INFO = (
    "GPU (CuPy/CUDA) — el mismo cálculo en la tarjeta gráfica. Puede ser 10–100× más "
    "rápido en mapas muy grandes (cientos de miles de curvas), pero requiere una GPU "
    "NVIDIA con CUDA y el paquete «cupy» instalado."
)


def _gpu_available() -> bool:
    try:
        import cupy  # noqa: F401

        return bool(cupy.cuda.runtime.getDeviceCount())
    except Exception:  # noqa: BLE001 - sin cupy/CUDA o driver: simplemente no hay GPU
        return False


def available_backends() -> tuple[str, ...]:
    """Backends utilizables ahora mismo (``"cpu"`` siempre; ``"gpu"`` si hay CUDA)."""
    return ("cpu", "gpu") if _gpu_available() else ("cpu",)


def backend_info(backend: str) -> str:
    """Texto explicativo del backend (para el pop-up de la UI)."""
    return GPU_INFO if backend == "gpu" else CPU_INFO


def array_module(backend: str = "cpu") -> Any:
    """Devuelve el módulo de arreglos: ``numpy`` (cpu) o ``cupy`` (gpu, con fallback)."""
    if backend == "gpu" and _gpu_available():
        import cupy

        return cupy
    return np


def to_numpy(array: Any) -> np.ndarray:
    """Trae un arreglo de vuelta a NumPy (host), sea de NumPy o CuPy."""
    getter = getattr(array, "get", None)  # cupy.ndarray.get() → numpy
    return np.asarray(getter() if callable(getter) else array)

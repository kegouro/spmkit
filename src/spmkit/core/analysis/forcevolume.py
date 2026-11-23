"""Análisis de force-volume: corre un :class:`Recipe` por curva → mapas de propiedades.

Un :class:`ForceVolume` es una grilla de curvas de fuerza. Este módulo ejecuta el
mismo pipeline reproducible en cada curva y arma **mapas 2D** de las cantidades que
el pipeline expone en su contexto (módulo de Young, adhesión, disipación, R², punto
de contacto). Es lo que reemplaza los mapas de propiedades mecánicas de ANA/JPK.

Ejecución secuencial por defecto; opcionalmente **en paralelo** con
``ProcessPoolExecutor`` (posible porque el ``loader`` del volumen es picklable), lo
que importa para mapas grandes (miles de curvas).
"""

from __future__ import annotations

import math
import os
from collections import deque
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from itertools import islice
from multiprocessing import get_context
from numbers import Real
from typing import Any

import numpy as np

from spmkit.core.models import ForceVolume
from spmkit.core.pipeline import Recipe, run

#: Cantidades del contexto del pipeline que se mapean por defecto.
DEFAULT_KEYS = (
    "young_modulus",
    "adhesion",
    "dissipation",
    "r_squared",
    "contact_point",
    "max_force",
    "max_indentation",
)

#: Unidad física (SI) de cada propiedad mapeable — fuente única para exportar con fidelidad.
PROPERTY_UNITS: dict[str, str] = {
    "young_modulus": "Pa",
    "young_modulus_std": "Pa",
    "adhesion": "N",
    "work_of_adhesion": "J/m²",
    "dissipation": "J",
    "r_squared": "",
    "contact_point": "m",
    "max_force": "N",
    "max_indentation": "m",
}

ProgressCallback = Callable[[float, int], None]


@dataclass(frozen=True)
class VolumeResult:
    """Mapas de propiedades de un force-volume y su estadística."""

    maps: dict[str, np.ndarray]  # nombre -> arreglo 2D (grid_shape)
    grid_shape: tuple[int, int]
    n_ok: int
    n_failed: int
    keys: tuple[str, ...] = field(default_factory=tuple)
    first_error: str = ""

    def stats(self, key: str) -> dict[str, float]:
        """Estadística robusta (ignorando NaN) de un mapa: media, mediana, σ, mín, máx."""
        arr = self.maps[key]
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return {
                "mean": float("nan"),
                "median": float("nan"),
                "std": float("nan"),
                "min": float("nan"),
                "max": float("nan"),
                "n": 0,
            }
        return {
            "mean": float(np.mean(finite)),
            "median": float(np.median(finite)),
            "std": float(np.std(finite)),
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "n": int(finite.size),
        }

    def histogram(self, key: str, bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
        """Histograma (counts, bordes) de un mapa, ignorando NaN."""
        arr = self.maps[key]
        finite = arr[np.isfinite(arr)]
        return np.histogram(finite, bins=bins)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["maps"] = {k: v.tolist() for k, v in self.maps.items()}
        return d


# --- ejecución paralela: estado por proceso worker (evita picklear todo por tarea) ---
_WORKER: dict[str, Any] = {}
_CurveResult = tuple[dict[str, float] | None, str]


def _init_worker(loader: Callable[[int], Any], recipe: Recipe, keys: tuple[str, ...]) -> None:
    _WORKER["loader"] = loader
    _WORKER["recipe"] = recipe
    _WORKER["keys"] = keys


def _run_curve(
    loader: Callable[[int], Any], recipe: Recipe, keys: tuple[str, ...], index: int
) -> _CurveResult:
    try:
        _, ctx = run(recipe, loader(index))
        values = {}
        for key in keys:
            value = ctx.get(key)
            if isinstance(value, (Real, np.bool_)) and math.isfinite(value):
                values[key] = float(value)
        return values, ""
    except Exception as exc:  # noqa: BLE001 - una curva mala no aborta el mapa
        return None, str(exc) or type(exc).__name__


def _run_chunk(start: int, stop: int) -> list[_CurveResult]:
    return [
        _run_curve(_WORKER["loader"], _WORKER["recipe"], _WORKER["keys"], index)
        for index in range(start, stop)
    ]


def analyze_volume(
    volume: ForceVolume,
    recipe: Recipe,
    keys: tuple[str, ...] = DEFAULT_KEYS,
    parallel: bool = False,
    max_workers: int | None = None,
    progress: ProgressCallback | None = None,
) -> VolumeResult:
    """Corre ``recipe`` en cada curva del volumen y arma los mapas de ``keys``.

    Args:
        keys: Nombres de campos del contexto del pipeline a mapear.
        parallel: Si es ``True``, usa procesos (``ProcessPoolExecutor``).
        progress: Callback ``(fracción, índice)`` tras cada curva.
    """
    n = volume.n_curves
    flat = {key: np.full(n, np.nan) for key in keys}
    n_ok = 0
    first_error = ""

    def store(index: int, result: _CurveResult) -> None:
        nonlocal n_ok, first_error
        values, error = result
        if values is None:
            if not first_error:
                first_error = f"Curva {index + 1}: {error}"
        else:
            n_ok += 1
            for key, value in values.items():
                flat[key][index] = value
        if progress is not None:
            progress((index + 1) / n, index)

    if parallel and max_workers is not None and max_workers < 1:
        raise ValueError("max_workers debe ser positivo")
    if parallel and n > 1 and (max_workers is not None or n >= 32):
        workers = min(n, max_workers or min(4, os.cpu_count() or 1))
        chunk_size = max(1, min(32, n // (workers * 2)))
        starts = iter(range(0, n, chunk_size))
        # spawn evita heredar el estado de Qt cuando el pool se abre desde un hilo.
        # Limitar los bloques enviados también acota el trabajo pendiente al cancelar.
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=get_context("spawn"),
            initializer=_init_worker,
            initargs=(volume.loader, recipe, keys),
        ) as executor:
            pending = deque(
                executor.submit(_run_chunk, start, min(start + chunk_size, n))
                for start in islice(starts, workers)
            )
            index = 0
            try:
                while pending:
                    chunk = pending.popleft().result()
                    start = next(starts, None)
                    if start is not None:
                        pending.append(
                            executor.submit(_run_chunk, start, min(start + chunk_size, n))
                        )
                    for result in chunk:
                        store(index, result)
                        index += 1
            finally:
                for future in pending:
                    future.cancel()
    else:
        for index in range(n):
            store(index, _run_curve(volume.curve, recipe, keys, index))

    return VolumeResult(
        maps={key: values.reshape(volume.grid_shape) for key, values in flat.items()},
        grid_shape=volume.grid_shape,
        n_ok=n_ok,
        n_failed=n - n_ok,
        keys=tuple(keys),
        first_error=first_error,
    )

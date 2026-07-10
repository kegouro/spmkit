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

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
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


def _init_worker(loader: Callable[[int], Any], recipe: Recipe, keys: tuple[str, ...]) -> None:
    _WORKER["loader"] = loader
    _WORKER["recipe"] = recipe
    _WORKER["keys"] = keys


def _run_index(index: int) -> dict[str, Any] | None:
    try:
        _, ctx = run(_WORKER["recipe"], _WORKER["loader"](index))
        return {k: ctx.get(k) for k in _WORKER["keys"]}
    except Exception:  # noqa: BLE001 - una curva mala no aborta el mapa
        return None


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
    results: list[dict[str, Any] | None] = [None] * n

    if parallel:
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=(volume.loader, recipe, keys),
        ) as executor:
            for i, res in enumerate(executor.map(_run_index, range(n))):
                results[i] = res
                if progress is not None:
                    progress((i + 1) / n, i)
    else:
        for i in range(n):
            try:
                _, ctx = run(recipe, volume.curve(i))
                results[i] = {k: ctx.get(k) for k in keys}
            except Exception:  # noqa: BLE001 - una curva mala no aborta el mapa
                results[i] = None
            if progress is not None:
                progress((i + 1) / n, i)

    rows, cols = volume.grid_shape
    maps: dict[str, np.ndarray] = {}
    for key in keys:
        flat = np.full(n, np.nan)
        for i, res in enumerate(results):
            if res is not None:
                value = res.get(key)
                if value is not None and np.isfinite(value):
                    flat[i] = float(value)
        maps[key] = flat.reshape(rows, cols)

    n_ok = sum(res is not None for res in results)
    return VolumeResult(
        maps=maps, grid_shape=volume.grid_shape, n_ok=n_ok, n_failed=n - n_ok, keys=tuple(keys)
    )

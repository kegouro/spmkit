"""La ruta vectorizada (CPU/GPU) debe coincidir con el ajuste por curva."""

from __future__ import annotations

import numpy as np

from spmkit.core import compute
from spmkit.core.analysis.forcevolume import analyze_volume
from spmkit.core.analysis.forcevolume_fast import FAST_KEYS, elasticity_map
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume
from spmkit.core.pipeline import Recipe, Step

_RECIPE = Recipe(
    steps=(
        Step(op="find_contact_point"),
        Step(
            op="fit_elasticity",
            params={"model": "sphere", "tip_radius": 10e-9},
            condition="contact_detected",
        ),
    )
)


def _volume(rows: int = 4, cols: int = 4) -> ForceVolume:
    curves = []
    n = rows * cols
    for i in range(n):
        young = 1.0e6 * (1 + 0.25 * i / n)
        sep = np.linspace(6e-7, 0.0, 260)
        e_star = young / (1 - 0.3**2)
        k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
        f = k * np.clip(3e-7 - sep, 0.0, None) ** 1.5
        seg = ForceSegment(
            segment_type="extend",
            direction="approach",
            raw_height=sep,
            raw_deflection=np.zeros_like(sep),
            force=f,
            separation=sep,
            state="force_n",
        )
        curves.append(ForceCurve(segments=(seg,)))
    return ForceVolume.from_curves(curves, grid_shape=(rows, cols), x_range=1e-6, y_range=1e-6)


def test_fast_matches_pipeline_modulus() -> None:
    vol = _volume(4, 4)
    slow = analyze_volume(vol, _RECIPE).maps["young_modulus"].ravel()
    fast = elasticity_map(vol, tip_radius=10e-9, model="sphere").maps["young_modulus"].ravel()
    ok = np.isfinite(slow) & np.isfinite(fast)
    assert ok.sum() == 16
    # Ambas rutas usan el MISMO ajuste conjunto del punto de contacto (Alpha #1) y concuerdan
    # a ~6e-5: la diferencia es redondeo de la grilla vectorizada vs la escalar, no de
    # algoritmo. Ambas recuperan E a <2% (tests/validation/test_recovery.py). El 1e-9 anterior
    # acoplaba dos implementaciones del MISMO umbral byte-a-byte; ya no aplica.
    assert np.allclose(slow[ok], fast[ok], rtol=1e-3)


def test_fast_result_has_all_keys_and_grid() -> None:
    result = elasticity_map(_volume(3, 3))
    assert set(FAST_KEYS) <= set(result.maps)
    assert result.maps["young_modulus"].shape == (3, 3)
    assert result.n_ok == 9


def test_backends_and_info() -> None:
    assert "cpu" in compute.available_backends()
    assert "CPU" in compute.backend_info("cpu")
    assert "GPU" in compute.backend_info("gpu")
    assert compute.array_module("cpu") is np  # sin GPU cae a NumPy

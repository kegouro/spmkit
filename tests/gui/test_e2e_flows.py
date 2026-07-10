"""E2E de los flujos de Fathom con data SINTÉTICA: cargar → perspectivas → resultado sensato.

Complementa el smoke (que solo ejercita fuerza): aquí cada flujo carga por el hub real y
verifica que la cadena produce un resultado definido (no solo "no crashea"). Data sintética
únicamente — nunca datos de instrumento.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.gui.app_workspace import build_workspace


def _topography() -> SPMData:
    """Topografía sintética con un montículo + un canal CPD (para KPFM)."""
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:64, 0:64]
    z = 2e-8 * np.exp(-((xx - 32) ** 2 + (yy - 24) ** 2) / 80.0) + 1e-9 * rng.standard_normal(
        (64, 64)
    )
    cpd = np.full((64, 64), 0.3) + 1e-3 * rng.standard_normal((64, 64))
    return SPMData(
        channels=(
            SPMChannel("Z-Axis", z, "m", 5e-6, 5e-6, direction="forward"),
            SPMChannel("CPD", cpd, "V", 5e-6, 5e-6, direction="forward"),
        ),
        metadata={"format": "nid"},
    )


def _thermal(f0: float = 72_800.0, q: float = 106.0) -> SPMData:
    """Espectro de sintonía térmica sintético (pico SHO en f0) que extract_thermal lee."""
    n = 2000
    f = np.linspace(30e3, 120e3, n)
    r = f / f0
    psd = 1e-12 / np.sqrt((1 - r**2) ** 2 + (r / q) ** 2)
    ch = SPMChannel(
        "Amplitude Spectral Density",
        psd.reshape(1, -1),
        "m",
        1.0,
        1.0,
        group="Spectrum FFT",
        metadata={"Dim0Min": 30e3, "Dim0Range": 90e3},
    )
    return SPMData(
        channels=(ch,),
        metadata={
            "info": {"Frequency:": "72.8 kHz", "Q Factor:": "106", "Spring Constant:": "1.175 N/m"}
        },
    )


def test_e2e_force_flow(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    fvm = ws.panel("force_canvas")._vm
    fvm.set_volume(synthetic_volume(9))
    fvm.run_fit_now()
    for persp in ("force", "smfs", "map", "batch"):
        ws.set_perspective(persp)
        assert ws.active_perspective == persp
    ws.set_perspective("map")
    mvm = ws.panel("map_canvas")._vm
    mvm.compute_now("pipeline")
    assert mvm.result is not None  # el mapa de módulo se calculó (grilla definida)
    for key in ("force_canvas", "map_canvas", "smfs_canvas", "batch_table"):
        assert not ws.panel(key).errored


def test_e2e_image_flow(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    ivm = ws.panel("navigator")._image_vm
    ivm.set_data(_topography())
    for persp in ("image", "grains", "spectral"):
        ws.set_perspective(persp)
        assert ws.active_perspective == persp
    assert ivm.roughness() is not None  # la rugosidad se computa sobre la topografía
    for key in ("image_canvas", "grains_canvas", "spectral_canvas"):
        assert not ws.panel(key).errored


def test_e2e_resonance_flow(qtbot) -> None:  # type: ignore[no-untyped-def]
    ws = build_workspace()
    qtbot.addWidget(ws)
    ivm = ws.panel("navigator")._image_vm
    ivm.set_data(_thermal())
    ws.set_perspective("resonance")
    rvm = ws.panel("resonance_canvas")._vm
    assert rvm.result is not None
    assert abs(rvm.result.peak.f0 - 72_800.0) < 500.0  # recupera f0 del pico sintético
    assert not ws.panel("resonance_canvas").errored

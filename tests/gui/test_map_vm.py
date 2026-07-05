"""Tests del MapViewModel: cálculo de mapa, motores CPU/GPU, linked brushing."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis.forcevolume import VolumeResult
from spmkit.gui.viewmodels import ForceViewModel, MapViewModel


def test_compute_now_builds_property_maps(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    fvm.set_volume(synthetic_volume(4))
    mvm = MapViewModel(fvm)
    seen = []
    mvm.mapReady.connect(seen.append)
    mvm.compute_now()
    assert isinstance(mvm.result, VolumeResult)
    assert seen and isinstance(seen[-1], VolumeResult)
    assert mvm.result.grid_shape == (1, 4)
    assert mvm.result.n_ok == 4
    assert "young_modulus" in mvm.result.maps


def test_fast_and_pipeline_engines_agree(synthetic_volume) -> None:
    fvm = ForceViewModel()
    fvm.set_volume(synthetic_volume(6))
    mvm = MapViewModel(fvm)
    mvm.compute_now("fast_cpu")
    fast = mvm.result.maps["young_modulus"].copy()
    mvm.compute_now("pipeline")
    slow = mvm.result.maps["young_modulus"]
    ok = np.isfinite(fast) & np.isfinite(slow)
    assert ok.sum() == 6
    assert np.allclose(fast[ok], slow[ok], rtol=1e-9)  # motores coinciden


def test_nonstandard_recipe_falls_back_to_pipeline(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    fvm.set_volume(synthetic_volume(4))
    fvm.set_params(smooth_window=11)  # suavizado → la ruta rápida no lo honra
    mvm = MapViewModel(fvm)
    msgs: list = []
    mvm.statusChanged.connect(msgs.append)
    with qtbot.waitSignal(mvm.mapReady, timeout=3000):
        mvm.compute("fast_cpu")
    assert any("pipeline" in m for m in msgs)  # avisó del fallback
    assert mvm.result is not None


def test_select_drives_shared_curve(synthetic_volume) -> None:
    fvm = ForceViewModel()
    fvm.set_volume(synthetic_volume(4))
    mvm = MapViewModel(fvm)
    mvm.select(2)
    assert fvm.index == 2  # linked brushing: mapa → curva activa


def test_new_volume_invalidates_map(synthetic_volume) -> None:
    fvm = ForceViewModel()
    fvm.set_volume(synthetic_volume(3))
    mvm = MapViewModel(fvm)
    mvm.compute_now()
    assert mvm.result is not None
    fvm.set_volume(synthetic_volume(2))  # emite volumeChanged
    assert mvm.result is None  # el mapa se invalida


def test_set_key_emits(synthetic_volume) -> None:
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    seen = []
    mvm.keyChanged.connect(seen.append)
    mvm.set_key("adhesion")
    assert mvm.key == "adhesion"
    assert seen == ["adhesion"]

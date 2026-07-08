"""Tests del SmfsViewModel: corre el pipeline de cadena sobre el retract de la curva activa."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis import chain
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume
from spmkit.gui.viewmodels import ForceViewModel, SmfsViewModel

_LP = 0.4e-9


def _retract_sawtooth(contours=(70e-9, 95e-9, 120e-9)):
    """(sep, force) de un retract sawtooth: N eventos WLC (sube → ruptura → 0) + cola libre."""
    seps, forces, start = [], [], 0.0
    for c in contours:
        x = np.linspace(0.0, 0.9 * c, 130)
        seps.append(start + x)
        forces.append(chain.wlc_force(x, c, _LP))
        start = start + 0.9 * c + 12e-9
    tail = np.linspace(start, start + 200e-9, 220)
    seps.append(tail)
    forces.append(np.zeros_like(tail))
    return np.concatenate(seps), np.concatenate(forces)


def _smfs_volume(n: int = 3) -> ForceVolume:
    sep, f = _retract_sawtooth()
    curves = []
    for _ in range(n):
        seg = ForceSegment(
            segment_type="retract",
            direction="retract",
            raw_height=sep,
            raw_deflection=np.zeros_like(sep),
            force=f,
            separation=sep,
            state="force_n",
        )
        curves.append(ForceCurve(segments=(seg,)))
    return ForceVolume.from_curves(curves, grid_shape=(1, n), x_range=1e-6, y_range=1e-6)


def test_smfs_vm_detecta_y_ajusta_eventos(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    seen: list = []
    svm.resultChanged.connect(seen.append)
    fvm.set_volume(_smfs_volume())  # curveChanged → compute()

    assert svm.result is not None
    assert len(svm.result.events) == 3  # sawtooth de 3 eventos
    assert len(svm.result.overlays) == 3  # un overlay por evento
    contours = sorted(ef.fit.contour_length for ef in svm.result.events)
    for got, want in zip(contours, (70e-9, 95e-9, 120e-9), strict=True):
        assert abs(got - want) / want < 0.06
    assert seen and seen[-1] is svm.result


def test_smfs_vm_cambia_de_modelo(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    fvm.set_volume(_smfs_volume())
    models: list = []
    svm.modelChanged.connect(models.append)
    svm.set_model("fjc")
    assert svm.model == "fjc"
    assert models == ["fjc"]
    assert svm.result is not None and svm.result.model == "fjc"


def test_smfs_vm_sin_volumen_emite_none(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    svm.compute()
    assert svm.result is None

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


def test_smfs_panel_dibuja_eventos_y_tabla(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.smfs_canvas import SmfsCanvasPanel

    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    panel = SmfsCanvasPanel(svm)
    qtbot.addWidget(panel)
    assert not panel.errored
    fvm.set_volume(_smfs_volume())
    assert panel._table.rowCount() == 3  # una fila por evento
    assert "3 eventos" in panel._readout.text()
    assert len(panel._plot.listDataItems()) >= 4  # retract + 3 overlays


def test_smfs_panel_cambia_modelo_actualiza_encabezado(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.smfs_canvas import SmfsCanvasPanel

    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    panel = SmfsCanvasPanel(svm)
    qtbot.addWidget(panel)
    fvm.set_volume(_smfs_volume())
    panel._combo.setCurrentIndex(1)  # FJC
    assert svm.model == "fjc"
    assert panel._table.horizontalHeaderItem(2).text() == "b (nm)"  # Kuhn, no lp


def test_smfs_vm_umbral_editable_recalcula(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    fvm.set_volume(_smfs_volume())
    assert len(svm.result.events) == 3
    changed: list = []
    svm.paramsChanged.connect(changed.append)
    svm.set_param("min_prominence_sigma", 1e9)  # nada supera esa prominencia
    assert changed and changed[-1]["min_prominence_sigma"] == 1e9
    assert svm.result is not None and len(svm.result.events) == 0  # el umbral editó el resultado


def test_smfs_panel_spins_reflejan_y_editan_params(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.smfs_canvas import SmfsCanvasPanel

    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    panel = SmfsCanvasPanel(svm)
    qtbot.addWidget(panel)
    assert panel._spins["min_r_squared"].value() == 0.95  # refleja el default del VM
    panel._spins["min_r_squared"].setValue(0.80)
    assert svm.params["min_r_squared"] == 0.80  # el control edita el VM


def test_smfs_vm_wlc_variant_y_temperatura(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    fvm.set_volume(_smfs_volume())
    assert svm.wlc_model == "bouchiat"
    seen: list = []
    svm.wlcModelChanged.connect(seen.append)
    svm.set_wlc_model("marko_siggia")
    assert svm.wlc_model == "marko_siggia" and seen == ["marko_siggia"]
    assert svm.result is not None and len(svm.result.events) == 3  # sigue detectando
    svm.set_param("temperature", 310.0)  # 37 °C
    assert svm.params["temperature"] == 310.0 and svm.result is not None


def test_smfs_panel_wlc_combo_solo_para_wlc(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.panels.smfs_canvas import SmfsCanvasPanel

    fvm = ForceViewModel()
    svm = SmfsViewModel(fvm)
    panel = SmfsCanvasPanel(svm)
    qtbot.addWidget(panel)
    assert panel._wlc_combo.isEnabled()  # WLC por defecto
    assert abs(panel._temp.value() - 24.85) < 0.1  # 298 K → 24.85 °C
    panel._combo.setCurrentIndex(1)  # FJC
    assert not panel._wlc_combo.isEnabled()  # la variante no aplica al FJC

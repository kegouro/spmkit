"""Tests del panel de pipeline en vivo: edición de parámetros → receta → re-ajuste."""

from __future__ import annotations

import numpy as np

from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume
from spmkit.gui.panels.pipeline_panel import PipelinePanel
from spmkit.gui.viewmodels import ForceViewModel


def _invols_volume(invols: float = 30e-9) -> ForceVolume:
    """Curva de contacto con InVOLS conocido: en contacto, altura = InVOLS · voltios."""
    volts = np.linspace(0.0, 2.0, 200)  # V
    height = invols * volts  # m
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=height,
        raw_deflection=volts,
        state="raw_v",
    )
    return ForceVolume.from_curves(
        [ForceCurve(segments=(seg,))], grid_shape=(1, 1), x_range=1e-6, y_range=1e-6
    )


def test_model_change_updates_recipe_and_enables(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    panel._model.setCurrentIndex(panel._model.findData("cone"))
    step = vm.recipe.steps[-1]
    assert step.op == "fit_elasticity"
    assert step.params["model"] == "cone"
    assert "half_angle" in step.params
    assert panel._angle.isEnabled()
    assert not panel._radius.isEnabled()


def test_radius_change_reemits_recipe(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    seen: list = []
    vm.recipeChanged.connect(seen.append)
    panel._radius.setValue(25.0)
    assert seen  # se re-emitió la receta
    assert abs(vm.recipe.steps[-1].params["tip_radius"] - 25e-9) < 1e-12


def test_calibration_override_maps_units(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    panel._invols.setValue(50.0)  # nm/V → m/V
    panel._k.setValue(2.5)
    cal = vm.recipe.steps[0]
    assert cal.op == "calibrate"
    assert abs(cal.params["invols"] - 50e-9) < 1e-15
    assert cal.params["spring_constant"] == 2.5


def test_smoothing_adds_step_to_recipe(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    panel._smooth.setValue(15)
    ops = [s.op for s in vm.recipe.steps]
    assert "smooth" in ops
    assert vm.recipe.steps[ops.index("smooth")].params["window"] == 15
    panel._smooth.setValue(0)
    assert "smooth" not in [s.op for s in vm.recipe.steps]


def test_contact_method_and_ksigma_reach_recipe(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]  # noqa: E501
    vm = ForceViewModel()
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    fit = vm.recipe.steps[-1]
    assert fit.params["contact_method"] == "joint"  # default robusto
    panel._contact.setCurrentIndex(panel._contact.findData("threshold"))
    panel._ksigma.setValue(7.0)
    fit = vm.recipe.steps[-1]
    assert fit.params["contact_method"] == "threshold"  # el combo edita la receta
    assert fit.params["k_sigma"] == 7.0


def test_mc_uncertainty_enables_and_computes(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]  # noqa: E501
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    assert not panel._invols_err.isEnabled()  # controles MC deshabilitados sin activar
    panel._mc.setChecked(True)
    panel._mc_n.setValue(30)  # pocas muestras: rápido
    assert panel._invols_err.isEnabled()
    fit = vm.recipe.steps[-1]
    assert fit.params["mc"] is True and fit.params["mc_samples"] == 30
    ctx: dict = {}
    vm.resultsChanged.connect(ctx.update)
    vm.run_fit_now()
    assert ctx.get("young_modulus_std", 0) > 0  # el MC produce una incertidumbre > 0


def test_estimate_invols_recovers_known_value() -> None:
    vm = ForceViewModel()
    vm.set_volume(_invols_volume(30e-9))
    est = vm.estimate_invols()
    assert est is not None and abs(est - 30e-9) / 30e-9 < 0.01  # recupera el InVOLS conocido


def test_invols_button_fills_control(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(_invols_volume(30e-9))
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    panel._calc_invols()  # botón "Calcular"
    assert abs(panel._invols.value() - 30.0) < 0.5  # 30e-9 m/V → ~30 nm/V en el control


def test_cone_fit_runs_end_to_end(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    panel = PipelinePanel(vm)
    qtbot.addWidget(panel)
    panel._model.setCurrentIndex(panel._model.findData("cone"))
    ctx: dict = {}
    vm.resultsChanged.connect(ctx.update)
    vm.run_fit_now()
    assert ctx.get("young_modulus", 0) > 0  # el ajuste cónico corre sin romper

"""Tests del panel de pipeline en vivo: edición de parámetros → receta → re-ajuste."""

from __future__ import annotations

from spmkit.gui.panels.pipeline_panel import PipelinePanel
from spmkit.gui.viewmodels import ForceViewModel


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

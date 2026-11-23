import json

import numpy as np
from PyQt6.QtWidgets import QFileDialog

from spmkit.core.analysis.forcevolume import analyze_volume
from spmkit.gui.app_workspace import _export_all, _export_results, build_workspace


def test_bundle_uses_the_active_recipe(qtbot, synthetic_volume, tmp_path, monkeypatch):
    import spmkit.core.forceexport as exports
    import spmkit.gui.runtime.tasks as tasks

    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    vm.set_volume(synthetic_volume(3))
    vm.set_params(tip_radius=40e-9, smooth_window=7, fit_min=1e-7, fit_max=2.5e-7)
    vm.source_path = str(tmp_path / "acquisition.nid")
    expected = analyze_volume(vm.volume, vm.recipe)
    original = exports.export_bundle
    monkeypatch.setattr(
        exports, "export_bundle", lambda *a, **kw: original(*a, **kw, report_formats=())
    )
    monkeypatch.setattr(tasks, "run_task", lambda task: task.run())
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
    _export_all(ws, vm)
    values = np.loadtxt(tmp_path / "mapa_young_modulus.csv", delimiter=",")
    np.testing.assert_allclose(values.ravel(), expected.maps["young_modulus"].ravel())
    meta = json.loads((tmp_path / "analisis.json").read_text())
    assert meta["recipe"] == json.loads(json.dumps(vm.recipe.to_dict()))
    assert meta["source"] == "acquisition.nid"


def test_json_handles_nonfinite_and_write_failure(qtbot, synthetic_volume, tmp_path, monkeypatch):
    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    vm._results_cache[0]["dissipation"] = float("nan")
    out = tmp_path / "result.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(out), ""))
    _export_results(ws, vm)
    data = json.loads(
        out.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
    )
    assert data["dissipation"] is None
    assert data["_analysis"]["recipe"] == vm.recipe.to_dict()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(tmp_path), ""))
    _export_results(ws, vm)
    assert "No se pudo exportar" in ws._status._message.text()


def test_recipe_clears_results_and_restores_controls(qtbot, synthetic_volume):
    ws = build_workspace()
    qtbot.addWidget(ws)
    vm = ws.panel("force_canvas")._vm
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    assert ws.panel("inspector")._values["young"].text() != "—"
    vm.set_params(tip_radius=5e-6, smooth_window=9, poisson=0.45)
    assert ws.panel("inspector")._values["young"].text() == "—"
    panel = ws.panel("pipeline")
    assert panel._radius.value() == 5000 and panel._smooth.value() == 9
    panel._poisson.setValue(0.4)
    assert vm.params["tip_radius"] == 5e-6 and vm.params["smooth_window"] == 9


def test_stale_map_completion_is_ignored(synthetic_volume, monkeypatch):
    import spmkit.gui.viewmodels.map_vm as module
    from spmkit.gui.viewmodels import ForceViewModel, MapViewModel

    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(2))
    map_vm = MapViewModel(vm)
    pending = []
    monkeypatch.setattr(module, "run_task", pending.append)
    map_vm.compute(engine="pipeline")
    vm.set_params(tip_radius=30e-9)
    pending[0].run()
    assert map_vm.result is None


def test_jkr_rejects_unsupported_options_instead_of_ignoring_them(synthetic_volume):
    import pytest

    from spmkit.core.pipeline import Recipe, Step, run

    for options in ({"mc": True}, {"fit_range": (1e-7, 2e-7)}):
        recipe = Recipe(steps=(Step("fit_elasticity", {"model": "jkr", **options}),))
        with pytest.raises(ValueError, match="JKR experimental"):
            run(recipe, synthetic_volume(1).curve(0))

"""Tests del ForceViewModel: señales, ajuste, curva calibrada y caché LRU."""

from __future__ import annotations

from spmkit.gui.viewmodels import DEFAULT_RECIPE, ForceViewModel


def test_set_volume_emits_and_resets(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    with qtbot.waitSignal(vm.volumeChanged, timeout=1000):
        vm.set_volume(synthetic_volume(3))
    assert vm.n_curves == 3
    assert vm.index == 0


def test_fit_recovers_modulus(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    ctx: dict = {}
    vm.resultsChanged.connect(ctx.update)
    vm.run_fit_now()
    assert ctx.get("contact_detected") is True
    assert abs(ctx["young_modulus"] - 1.0e6) / 1.0e6 < 0.15
    # Devuelve la curva calibrada del pipeline (para dibujar) y la línea de ajuste.
    assert vm.result_curve() is not None
    assert len(ctx["fit"].x_fit) > 0


def test_set_curve_out_of_range_ignored(synthetic_volume) -> None:
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(2))
    vm.set_curve(99)
    assert vm.index == 0
    vm.set_curve(-1)
    assert vm.index == 0
    vm.set_curve(1)
    assert vm.index == 1


def test_recipe_change_invalidates_cache(qtbot, synthetic_volume) -> None:  # type: ignore[no-untyped-def]
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(1))
    vm.run_fit_now()
    seen = []
    vm.recipeChanged.connect(lambda r: seen.append(r))
    vm.set_recipe(DEFAULT_RECIPE)
    assert seen == [DEFAULT_RECIPE]


def test_set_param_rebuilds_recipe(synthetic_volume) -> None:
    vm = ForceViewModel()
    vm.set_param("model", "cone")
    assert vm.params["model"] == "cone"
    assert vm.recipe.steps[-1].params["model"] == "cone"


def test_fit_range_param_enters_and_leaves_recipe(synthetic_volume) -> None:
    vm = ForceViewModel()
    vm.set_params(fit_min=1e-7, fit_max=3e-7)
    assert vm.recipe.steps[-1].params["fit_range"] == (1e-7, 3e-7)
    vm.set_params(fit_min=None, fit_max=None)
    assert "fit_range" not in vm.recipe.steps[-1].params


def test_curve_cache_survives_navigation(synthetic_volume) -> None:
    vm = ForceViewModel()
    vm.set_volume(synthetic_volume(3))
    first = vm.current_curve()
    vm.set_curve(2)
    vm.set_curve(0)
    assert vm.current_curve() is first  # cacheada, misma instancia

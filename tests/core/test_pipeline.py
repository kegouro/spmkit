"""Tests del motor de pipeline (Recipe, roundtrip YAML, condiciones seguras, run)."""

from __future__ import annotations

import pytest

from spmkit.core.pipeline import Recipe, Step, evaluate_condition, operation, run


def test_recipe_roundtrip_yaml() -> None:
    recipe = Recipe(
        name="standard_nanoindentation",
        steps=(
            Step(op="calibrate", params={"invols": 50.0e-9, "k": 0.2}),
            Step(
                op="fit_elasticity",
                params={"model": "hertz", "tip_radius": 20.0e-9},
                condition="contact_detected and r_squared > 0.9",
            ),
        ),
    )
    back = Recipe.from_yaml(recipe.to_yaml())
    assert back == recipe


def test_recipe_from_yaml_rejects_non_mapping() -> None:
    with pytest.raises(ValueError, match="mapeo"):
        Recipe.from_yaml("- just\n- a\n- list\n")


def test_evaluate_condition_basic() -> None:
    ctx = {"contact_detected": True, "r_squared": 0.95, "n_fit": 200}
    assert evaluate_condition("contact_detected and r_squared > 0.9", ctx) is True
    assert evaluate_condition("r_squared > 0.99", ctx) is False
    assert evaluate_condition("n_fit >= 200 or contact_detected", ctx) is True
    assert evaluate_condition("not contact_detected", ctx) is False


def test_evaluate_condition_rejects_unsafe() -> None:
    ctx = {"x": 1}
    with pytest.raises(ValueError):  # llamada a función: no permitida (seguridad)
        evaluate_condition("__import__('os').system('echo hi')", ctx)
    with pytest.raises(ValueError):  # atributo: no permitido (seguridad)
        evaluate_condition("x.__class__", ctx)


def test_evaluate_condition_missing_name_is_falsy() -> None:
    """Un nombre ausente es indefinido (falso), para poder saltar pasos del pipeline."""
    ctx = {"x": 1}
    assert evaluate_condition("y", ctx) is False
    assert evaluate_condition("y > 0", ctx) is False
    assert evaluate_condition("x > 0 and missing", ctx) is False


# Operaciones de prueba (las reales de física se registran en fases posteriores).
@operation("test_set_flag")
def _op_set_flag(target: object, ctx: dict, value: bool = True) -> object:
    ctx["flag"] = value
    return target


@operation("test_add_tag")
def _op_add_tag(target: object, ctx: dict, tag: str = "x") -> object:
    ctx.setdefault("tags", []).append(tag)
    return target


def test_run_executes_steps_and_respects_conditions() -> None:
    recipe = Recipe(
        steps=(
            Step(op="test_set_flag", params={"value": True}),
            Step(op="test_add_tag", params={"tag": "a"}, condition="flag == True"),
            Step(op="test_add_tag", params={"tag": "b"}, condition="flag == False"),
        )
    )
    progress: list[tuple[float, str]] = []
    result, ctx = run(recipe, target="obj", progress=lambda f, name: progress.append((f, name)))

    assert result == "obj"
    assert ctx["flag"] is True
    assert ctx["tags"] == ["a"]  # el paso con condición flag==False se saltó
    assert len(progress) == 2  # solo los pasos ejecutados invocan el callback

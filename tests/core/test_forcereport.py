"""Tests del informe de espectroscopía de fuerza (HTML/LaTeX/PDF)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("jinja2")

from spmkit.core.forcereport import (  # noqa: E402
    _latexify,
    _which_latex,
    build_force_report,
)
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume  # noqa: E402


def _volume(n: int = 9) -> ForceVolume:
    curves = []
    for _ in range(n):
        sep = np.linspace(6e-7, 0.0, 200)
        e_star = 1.0e6 / (1 - 0.3**2)
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
    return ForceVolume.from_curves(curves, grid_shape=(3, 3), x_range=1e-6, y_range=1e-6)


def test_latexify_converts_unicode() -> None:
    assert _latexify("10×10") == r"10$\times$10"
    assert "±" not in _latexify("a ± b")
    assert _latexify("R²") == r"R\textsuperscript{2}"


def test_report_html_and_latex(tmp_path) -> None:  # type: ignore[no-untyped-def]
    produced = build_force_report(
        _volume(9), tmp_path / "informe", source_name="test.nid", formats=("html", "latex")
    )
    assert produced["html"].exists()
    html = produced["html"].read_text(encoding="utf-8")
    assert "espectroscopía de fuerza" in html
    assert "Módulo de Young" in html
    assert "data:image/png;base64" in html  # figuras embebidas
    tex = produced["latex"].read_text(encoding="utf-8")
    assert r"\includegraphics" in tex
    assert r"$\times$" in tex  # unicode convertido a comando LaTeX


@pytest.mark.skipif(_which_latex() is None, reason="sin cadena LaTeX instalada")
def test_report_pdf(tmp_path) -> None:  # type: ignore[no-untyped-def]
    produced = build_force_report(
        _volume(9), tmp_path / "informe", source_name="t.nid", formats=("pdf",)
    )
    assert "pdf" in produced
    assert produced["pdf"].exists() and produced["pdf"].stat().st_size > 1000


def test_report_reuses_recipe_for_representative_curve(tmp_path, monkeypatch):
    import json

    import spmkit.core.viz
    from spmkit.core.analysis.forcevolume import analyze_volume
    from spmkit.core.pipeline import Recipe, Step

    recipe = Recipe(
        steps=(
            Step("find_contact_point"),
            Step(
                "fit_elasticity",
                {"model": "sphere", "tip_radius": 40e-9, "fit_range": (1e-7, 2.5e-7)},
            ),
        )
    )
    expected = analyze_volume(_volume(), recipe)
    captured = []
    original = spmkit.core.viz.save_force_curve

    def record(curve, ctx, path):
        captured.append(ctx["young_modulus"])
        return original(curve, ctx, path)

    monkeypatch.setattr(spmkit.core.viz, "save_force_curve", record)
    out = build_force_report(_volume(), tmp_path / "recipe", recipe=recipe, formats=("html",))
    assert captured[0] == pytest.approx(expected.stats("young_modulus")["median"])
    meta = json.loads(out["analysis"].read_text())
    assert meta["recipe"] == json.loads(json.dumps(recipe.to_dict()))

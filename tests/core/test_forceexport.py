"""Test de la exportación integral (mapas CSV, tabla, resumen, informe)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from spmkit.core.forceexport import export_bundle  # noqa: E402
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


def test_export_bundle_produces_all(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest = export_bundle(
        _volume(9), tmp_path / "exp", source_name="t.nid", report_formats=("html",)
    )
    assert (tmp_path / "exp" / "mapa_young_modulus.csv").exists()
    assert manifest["table"].exists()
    assert manifest["summary"].exists()
    assert manifest["report_html"].exists()
    # La tabla tiene cabecera + una fila por curva.
    lines = manifest["table"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 10  # header + 9 curvas
    assert lines[0].startswith("index,row,col,x_m,y_m,young_modulus")
    # El resumen lista propiedades.
    assert "young_modulus" in manifest["summary"].read_text(encoding="utf-8")

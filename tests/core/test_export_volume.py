"""Exportación científica de mapas de fuerza (force-volume) a CSV trazable."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis.forcevolume import VolumeResult
from spmkit.core.export import export_volume, to_csv


def _result() -> VolumeResult:
    # 2x2: young con datos (un punto fallido = NaN), adhesion con datos, dissipation TODO NaN.
    young = np.array([[1.0e6, 2.0e6], [3.0e6, np.nan]])
    adhesion = np.array([[1e-9, 2e-9], [3e-9, 4e-9]])
    dissipation = np.full((2, 2), np.nan)  # sin retract → todo NaN
    return VolumeResult(
        maps={"young_modulus": young, "adhesion": adhesion, "dissipation": dissipation},
        grid_shape=(2, 2),
        n_ok=3,
        n_failed=1,
        keys=("young_modulus", "adhesion", "dissipation"),
    )


def test_export_volume_cientifico(tmp_path) -> None:
    out = tmp_path / "mapa.csv"
    export_volume(_result(), out, source="test.jpk", extra_meta={"modelo": "sphere"})
    text = out.read_text(encoding="utf-8")

    # cabecera de metadatos
    assert "# fuente: test.jpk" in text
    assert "# modelo: sphere" in text
    assert "grilla: 2 x 2" in text and "curvas OK: 3" in text and "fallidas: 1" in text
    # dissipation es todo NaN → se omite con nota, NO se vuelca como columna de NaN
    assert "sin datos (omitidas): dissipation" in text
    assert "dissipation" not in text.split("datos por punto")[1]  # no en la tabla

    # estadística con unidad
    assert "young_modulus,Pa," in text
    assert "adhesion,N," in text
    # encabezado de la tabla por punto con unidades
    assert "young_modulus [Pa]" in text and "adhesion [N]" in text
    # el punto fallido queda vacío, no "nan"
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    data_rows = lines[lines.index("row,col,young_modulus [Pa],adhesion [N]") + 1 :]
    assert data_rows[-1].startswith("1,1,,")  # young NaN → celda vacía; adhesion presente
    assert "nan" not in text.lower()  # sin ningún NaN literal en el archivo


def test_to_csv_despacha_volume(tmp_path) -> None:
    out = tmp_path / "v.csv"
    to_csv(_result(), out)  # to_csv debe reconocer VolumeResult y delegar
    assert "force-volume" in out.read_text(encoding="utf-8")

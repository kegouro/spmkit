"""Tests del procesamiento por lotes de curvas de fuerza."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.forcebatch import ForceBatchResult, load_force, process_force_folder
from spmkit.core.pipeline import Recipe, Step

_SAMPLE_DIR = Path(__file__).resolve().parents[2] / "reference" / "sample_files"

_RECIPE = Recipe(
    steps=(
        Step(op="find_contact_point"),
        Step(op="fit_elasticity", params={"tip_radius": 10e-9}, condition="contact_detected"),
    )
)


def _make_jpk_force(path: Path) -> None:
    """.jpk-force sintético con una curva Hertz (fuerza en N ya escalada)."""
    n = 400
    sep = np.linspace(6e-7, 0.0, n)
    e_star = 1.0e6 / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    force_n = k * np.clip(3e-7 - sep, 0.0, None) ** 1.5  # N
    # height como int16 con encoder 1e-9 m/cuenta; vDeflection tal que force = raw·1e-12 N
    raw_h = np.round(sep / 1e-9).astype(">i2")
    raw_vd = np.round(force_n / 1e-12).astype(">i2")
    header = "\n".join(
        [
            "force-segment-header.name.name=extend-spm",
            "channel.height.data.type=short",
            "channel.height.data.encoder.scaling.multiplier=1.0E-9",
            "channel.height.data.encoder.scaling.offset=0.0",
            "channel.height.conversion-set.conversions.list=calibrated",
            "channel.height.conversion-set.conversion.calibrated.scaling.multiplier=1.0",
            "channel.height.conversion-set.conversion.calibrated.scaling.offset=0.0",
            "channel.vDeflection.data.type=short",
            "channel.vDeflection.data.encoder.scaling.multiplier=1.0",
            "channel.vDeflection.data.encoder.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversions.list=distance force",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.multiplier=1.0E-6",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversion.force.scaling.multiplier=1.0E-6",
            "channel.vDeflection.conversion-set.conversion.force.scaling.offset=0.0",
        ]
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("header.properties", "jpk-data-file=spm-forcefile\n")
        zf.writestr("segments/0/segment-header.properties", header)
        zf.writestr("segments/0/channels/height.dat", raw_h.tobytes())
        zf.writestr("segments/0/channels/vDeflection.dat", raw_vd.tobytes())


def test_load_force_dispatch(tmp_path: Path) -> None:
    jpk = tmp_path / "curve.jpk-force"
    _make_jpk_force(jpk)
    vol = load_force(jpk)
    assert vol.n_curves == 1


def test_load_force_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("no soy una curva")
    with pytest.raises(ValueError, match="no soportada"):
        load_force(bad)


def test_process_folder_and_csv(tmp_path: Path) -> None:
    for i in range(3):
        _make_jpk_force(tmp_path / f"c{i}.jpk-force")
    result = process_force_folder(tmp_path, _RECIPE)
    assert len(result.rows) == 3
    assert result.n_failed == 0
    assert all(r.n_curves == 1 for r in result.rows)

    out = tmp_path / "resumen.csv"
    result.to_csv(out)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    assert len(lines) == 4  # encabezado + 3 filas (sin contar los comentarios de metadatos)
    assert "young_modulus_median" in lines[0]


def test_empty_folder(tmp_path: Path) -> None:
    result = process_force_folder(tmp_path, _RECIPE)
    assert isinstance(result, ForceBatchResult)
    assert result.rows == []


@pytest.mark.skipif(not _SAMPLE_DIR.exists(), reason="carpeta de samples .nid no disponible")
def test_process_real_nid_folder() -> None:
    result = process_force_folder(_SAMPLE_DIR, _RECIPE)
    # al menos algún .nid de nanomecánica debe procesarse con curvas
    assert any(r.n_curves > 0 for r in result.rows)


def test_batch_csv_cientifico(tmp_path) -> None:
    """El resumen del batch lleva metadatos, unidades y celdas vacías (no NaN)."""
    from spmkit.core.forcebatch import ForceBatchRow

    result = ForceBatchResult(
        rows=[
            ForceBatchRow(
                source="a.jpk-force",
                n_curves=1,
                n_ok=1,
                young_modulus_median=1.5e6,
                adhesion_median=2e-9,
                # dissipation_median queda en NaN (sin retract)
            ),
            ForceBatchRow(source="b.jpk-force", error="curva inválida"),
        ]
    )
    out = tmp_path / "lote.csv"
    result.to_csv(out)
    text = out.read_text(encoding="utf-8")
    assert "lote de curvas/mapas" in text  # cabecera de metadatos
    assert "archivos: 2" in text and "OK: 1" in text and "fallidos: 1" in text
    assert "young_modulus_median [Pa]" in text  # unidad en el encabezado
    assert "dissipation_median [J]" in text
    assert "nan" not in text.lower()  # NaN → celda vacía, sin literal

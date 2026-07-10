"""Robustez ante entradas degeneradas — que nada crashee ni dé resultados basura.

Fija el comportamiento verificado por sondeo: imágenes planas/NaN, curvas sin contacto,
informe sin ajustes válidos. Software científico: fallar limpio o dar 0, nunca reventar.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume, SPMChannel


def _ch(data: np.ndarray, unit: str = "m") -> SPMChannel:
    return SPMChannel(name="Z", data=np.asarray(data, float), unit=unit, x_range=1e-6, y_range=1e-6)


def _flat_curve() -> ForceCurve:
    n = 200
    sep = np.linspace(6e-7, 0.0, n)
    z = np.zeros(n)
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=sep,
        raw_deflection=z,
        deflection=z,
        force=z,
        separation=sep,
        state="force_n",
    )
    return ForceCurve(segments=(seg, seg))


def _flat_volume(n: int = 4) -> ForceVolume:
    return ForceVolume.from_curves(
        tuple(_flat_curve() for _ in range(n)), grid_shape=(1, n), x_range=1e-6, y_range=1e-6
    )


# --------------------------------------------------------------------- imágenes


def test_grains_imagen_plana_da_cero() -> None:
    pytest.importorskip("scipy")
    from spmkit.core.analysis import grains

    assert grains.detect(_ch(np.zeros((16, 16)))).n_grains == 0  # sin relieve, sin crash


def test_grains_todo_nan_no_crashea() -> None:
    pytest.importorskip("scipy")
    from spmkit.core.analysis import grains

    assert grains.detect(_ch(np.full((16, 16), np.nan))).n_grains >= 0  # define resultado


def test_spectral_constante_no_crashea() -> None:
    from spmkit.core.analysis import spectral

    ch = _ch(np.ones((16, 16)))
    spectral.fractal_dimension(ch)  # no debe reventar con superficie plana
    assert spectral.radial_psd(ch).q.size > 1


def test_profile_p0_igual_p1() -> None:
    from spmkit.core.analysis import profiles

    prof = profiles.line(_ch(np.zeros((8, 8))), (3, 3), (3, 3))
    assert len(prof) >= 2  # segmento nulo → perfil trivial, sin ZeroDivision


# ------------------------------------------------------------------ curvas


def test_elasticity_map_sin_contacto_da_n_ok_cero() -> None:
    from spmkit.core.analysis.forcevolume_fast import elasticity_map

    assert elasticity_map(_flat_volume()).n_ok == 0  # ningún ajuste válido, sin crash


def test_report_sin_ajustes_validos_da_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("matplotlib")
    from spmkit.core.forcereport import build_force_report

    with pytest.raises(ValueError, match="NaN|graficabl"):
        build_force_report(_flat_volume(), tmp_path / "rep", formats=("html",))


# ---------------------------------------------------------- archivos corruptos/vacíos


def _write_nid(path, header: str, raw: bytes = b"") -> None:
    path.write_bytes(header.encode("latin-1") + b"#!" + raw)


def test_nid_canal_sin_points_da_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Un .nid truncado (canal sin Points/Lines) → ValueError claro, no KeyError."""
    from spmkit.core.io.nid import load_nid

    header = (
        "[DataSet]\r\nGroupCount=1\r\nGr0-Count=1\r\nGr0-Ch0=DataSet-0:0\r\n\r\n"
        "[DataSet-0:0]\r\nLines=8\r\nDim2Name=Z-Axis\r\n"  # falta Points
    )
    p = tmp_path / "bad.nid"
    _write_nid(p, header)
    with pytest.raises(ValueError, match="corrupto"):
        load_nid(p)


def test_nid_sin_canales_da_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Un .nid sin canales (GroupCount=0) → ValueError, no SPMData vacío silencioso."""
    from spmkit.core.io.nid import load_nid

    p = tmp_path / "empty.nid"
    _write_nid(p, "[DataSet]\r\nGroupCount=0\r\n")
    with pytest.raises(ValueError, match="sin canales"):
        load_nid(p)


def test_jpk_force_corrupto_da_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Un .jpk-force con segmento pero sin sus canales → ValueError, no KeyError."""
    import zipfile

    from spmkit.core.io.jpk import load_jpk_force

    p = tmp_path / "bad.jpk-force"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("segments/0/segment-header.properties", "")  # sin channels/*.dat
    with pytest.raises(ValueError, match="corrupto|incompleto"):
        load_jpk_force(p)


def test_volume_vacio_da_valueerror() -> None:
    """Analizar un force-volume sin curvas → ValueError, no IndexError."""
    from spmkit.core.analysis.forcevolume_fast import elasticity_map

    vol = ForceVolume.from_curves((), grid_shape=(1, 0), x_range=1e-6, y_range=1e-6)
    with pytest.raises(ValueError):
        elasticity_map(vol)

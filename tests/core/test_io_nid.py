"""Tests del parser .nid."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit import load
from spmkit.core.io import load_nid, load_nid_force, supported_extensions

_NANOMECH_NID = (
    Path(__file__).resolve().parents[2]
    / "reference"
    / "sample_files"
    / "Image00860 nanomech small nanofiber.nid"
)


def test_supported_extensions() -> None:
    assert ".nid" in supported_extensions()
    assert ".nhf" in supported_extensions()


@pytest.mark.skipif(not _NANOMECH_NID.exists(), reason="sample .nid de nanomecánica no disponible")
def test_load_nid_force_volume() -> None:
    """La espectroscopía de un .nid real carga como ForceVolume con extend/retract."""
    vol = load_nid_force(_NANOMECH_NID)
    assert vol.n_curves > 0
    curve = vol.curve(vol.n_curves // 2)
    assert curve.extend is not None
    assert curve.extend.force is not None
    assert np.all(np.isfinite(curve.extend.force))
    assert curve.retract is not None  # este .nid tiene approach y retract


def test_load_nid_basic(nid_file: Path) -> None:
    data = load_nid(nid_file)
    assert data.names == ["Z-Axis"]
    ch = data["Z-Axis"]
    assert ch.shape == (8, 8)
    assert ch.unit == "m"
    assert ch.x_range == pytest.approx(5e-6)


def test_nid_physical_mapping(nid_file: Path) -> None:
    ch = load_nid(nid_file)["Z-Axis"]
    # raw=0 -> mitad del rango: dim2_min(-1) + 0.5*range(2) = 0.0
    assert ch.data[1, 1] == pytest.approx(0.0, abs=1e-9)
    # raw=2**30 en (fila 0, col 0) -> norm=(2**30+2**31)/2**32=0.75 -> -1+0.75*2 = 0.5.
    # El parser voltea verticalmente (orientación Gwyddion), así que aparece en la
    # última fila.
    assert ch.data[-1, 0] == pytest.approx(0.5, abs=1e-6)
    assert ch.data[0, 0] == pytest.approx(0.0, abs=1e-9)


def test_load_dispatch(nid_file: Path) -> None:
    assert load(nid_file).names == ["Z-Axis"]


def test_load_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("nope")
    with pytest.raises(ValueError, match="no soportado"):
        load(bad)


def test_nid_missing_marker(tmp_path: Path) -> None:
    bad = tmp_path / "bad.nid"
    bad.write_bytes(b"[DataSet]\r\nno marker here")
    with pytest.raises(ValueError, match="marcador"):
        load_nid(bad)


@pytest.mark.skipif(
    not list(Path(__file__).parents[2].glob("reference/sample_files/*.nid")),
    reason="sin archivos .nid reales en reference/",
)
def test_real_nid_files_load() -> None:
    """Si hay .nid reales en reference/, deben cargar sin error."""
    files = list(Path(__file__).parents[2].glob("reference/sample_files/*.nid"))
    data = load(files[0])
    assert len(data) > 0
    assert all(np.isfinite(c.data).all() for c in data.channels)

"""Tests del parser .nid."""

from __future__ import annotations

import hashlib
import struct
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
    assert vol.metadata["spring_constant"] == pytest.approx(2.66102, rel=1e-3)  # k del header


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


def test_public_nid_calibration_and_branch_pairing() -> None:
    from spmkit.core.pipeline import Recipe, Step, run

    fixture = (
        Path(__file__).resolve().parents[1]
        / "validation/fixtures/force_foundation/spectroscopy.nid"
    )
    volume = load_nid_force(fixture)
    assert volume.n_curves == 100
    k = volume.metadata["spring_constant"]
    assert k == pytest.approx(2.72436)
    digest = hashlib.sha256()
    for index in range(volume.n_curves):
        curve = volume.curve(index)
        for seg in curve.segments:
            np.testing.assert_array_equal(seg.deflection, seg.force / k)
            assert seg.metadata["force_input_unit"] == "N"
            # NSFopen 2.2.4 nid_read(..., dataframe=False).data["Spec"]:
            # Forward then Backward, Deflection then Z-Axis Sensor, acquisition order.
            for values in (seg.force, seg.raw_height):
                digest.update(struct.pack("<I", values.size))
                digest.update(np.asarray(values, dtype="<f8").tobytes())
            status = "matched"
            if index == 0:
                status = "force_mismatch"
            elif seg.force.size < seg.metadata["stored_force_points"]:
                status = "length_mismatch"
            assert seg.metadata["separation_status"] == status
            assert (seg.separation is None) == (status != "matched")
    assert digest.hexdigest() == "86a5c92fe889beb9cf5ba31a70d8f92f21cedb1954328c5da483fc1aea3323b2"
    _, result = run(Recipe(steps=(Step("calibrate"),)), volume.curve(0))
    assert result["fit_axis"] == "height"
    assert result["force_calibration_source"] == "nid_header_scaling"


def test_force_nid_requires_explicit_physical_scaling(tmp_path) -> None:
    from tests.core.test_annotated_force_steps import write_spectrum

    path = tmp_path / "missing-scale.nid"
    write_spectrum(path, "nN")
    path.write_bytes(path.read_bytes().replace(b"Dim2Range=65536\n", b"", 1))
    with pytest.raises(ValueError, match="falta escala física"):
        load_nid_force(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("SaveMode", "ASCII"),
        ("SaveOrder", "unknown"),
        ("SaveBits", "12"),
        ("SaveSign", "float"),
    ],
)
def test_unsupported_nid_encoding(nid_file, field, value):
    import re

    from spmkit.core.verify import trace_nid

    blob = re.sub(
        rb"(?m)^" + field.encode() + rb"=[^\r\n]+",
        f"{field}={value}".encode(),
        nid_file.read_bytes(),
    )
    nid_file.write_bytes(blob)
    with pytest.raises(ValueError, match=field):
        load(nid_file)
    assert not trace_nid(nid_file).ok


def test_missing_nid_channel_stops_decode(nid_file):
    from spmkit.core.io.readers import NidReader
    from spmkit.core.verify import trace_nid

    nid_file.write_bytes(
        nid_file.read_bytes()
        .replace(b"Gr0-Ch0=DataSet-0:0", b"Gr0-Ch0=missing\r\nGr0-Ch1=DataSet-0:0")
        .replace(b"Gr0-Count=1", b"Gr0-Count=2")
    )
    for read in (NidReader().inspect, load_nid):
        with pytest.raises(ValueError, match="missing"):
            read(nid_file)
    assert not trace_nid(nid_file).ok


def test_variable_length_nid_excludes_padding(tmp_path):
    from spmkit.core.analysis.mechanics import extract_curves
    from tests.core.test_annotated_force_steps import write_spectrum

    path = tmp_path / "variable.nid"
    write_spectrum(path, "nN")
    fields = b"LineDim0Points=5\nLineDim1Points=12\nLineDim0Min=7\nLineDim0Range=2\n"
    path.write_bytes(path.read_bytes().replace(b"Points=12\n", fields + b"Points=12\n"))
    legacy = extract_curves(load_nid(path).channels[0])
    np.testing.assert_array_equal(legacy[0].z, [7, 7.5, 8, 8.5, 9])
    np.testing.assert_array_equal(legacy[0].force, [0, 1, 2, 3, 4])
    volume = load_nid_force(path)
    np.testing.assert_array_equal(volume.curve(0).extend.force, np.arange(5) * 1e-9)
    assert volume.curve(1).extend.force.size == 12

    good = path.read_bytes()
    for replacement, error in (
        (b"", "incompleta"),
        (b"LineDim0Points=13\n", "rango"),
        (b"LineDim0Points=6\n", "incompatibles"),
    ):
        path.write_bytes(good.replace(b"LineDim0Points=5\n", replacement, 1))
        with pytest.raises(ValueError, match=error):
            load_nid_force(path)


def test_nid_mixed_width_and_byte_order(tmp_path):
    from spmkit.core.verify import trace_nid

    # Sparse slot indices; binary order follows group/channel indices even if
    # header entries appear in reverse order. Each physical scale is one unit/count.
    header = (
        "[DataSet]\nGroupCount=1\nGr0-Count=8\nGr0-Ch7=B\nGr0-Ch2=A\n"
        "[B]\nPoints=2\nLines=1\nSaveBits=32\nSaveOrder=Intel\n"
        "Dim2Min=-2147483648\nDim2Range=4294967296\n"
        "[A]\nPoints=3\nLines=1\nSaveBits=16\nSaveOrder=Motorola\n"
        "Dim2Min=-32760\nDim2Range=65536\n"
    )
    path = tmp_path / "mixed.nid"
    path.write_bytes(
        header.encode() + b"#!" + struct.pack(">3h", -10, 0, 513) + struct.pack("<2i", -120000, 7)
    )
    first, second = load_nid(path).channels
    np.testing.assert_array_equal(first.data, [[-2, 8, 521]])
    np.testing.assert_array_equal(second.data, [[-120000, 7]])
    trace = trace_nid(path)
    assert trace.ok
    assert [c.byte_length for c in trace.channels] == [6, 8]

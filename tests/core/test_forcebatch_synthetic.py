"""Batch regressions using only generated NanoSurf force maps."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.forcebatch import ForceBatchResult, process_force_folder
from spmkit.core.io.nid import load_nid_force
from spmkit.core.pipeline import Recipe, Step

RECIPE = Recipe((Step("calibrate"), Step("fit_elasticity")))


def write_force_map(
    path: Path, curves: int, bad: range = range(0), *, points: int = 96, retract: bool = False
) -> None:
    """Write Hertz approach curves with optional rows too short for a fit."""
    height = np.linspace(600.0, 0.0, points)
    force = (4 / 3) * 1e6 / (1 - 0.3**2) * np.sqrt(10e-9)
    force *= np.clip((300 - height) * 1e-9, 0, None) ** 1.5 * 1e9
    counts = (
        "".join(f"LineDim{i}Points={3 if i in bad else points}\n" for i in range(curves))
        if bad
        else ""
    )
    channels = [("Deflection", "nN", 64, force), ("Z-Axis Sensor", "nm", 1024, height)]
    if retract:
        channels += [
            ("Deflection", "nN", 64, force[::-1] * 0.9),
            ("Z-Axis Sensor", "nm", 1024, height[::-1]),
        ]
    header = f"[DataSet]\nGroupCount=1\nGr0-Count={len(channels)}\n"
    header += "".join(f"Gr0-Ch{i}=Channel-{i}\n" for i in range(len(channels)))
    payload = []
    for i, (name, unit, span, values) in enumerate(channels):
        frame = "Spec forward" if i < 2 else "Spec backward"
        header += (
            f"[Channel-{i}]\nPoints={points}\nLines={curves}\nFrame={frame}\n"
            f"Dim1Name=SpecPoint\nDim2Name={name}\nDim2Unit={unit}\n"
            f"Dim2Min=0\nDim2Range={span}\nSaveBits=32\n{counts}"
        )
        raw = np.round(values / span * 2**32 - 2**31).astype("<i4")
        payload.append(raw.tobytes() * curves)
    path.write_bytes(header.encode() + b"#!" + b"".join(payload))


def test_synthetic_force_maps_serial_parallel_and_csv(tmp_path: Path) -> None:
    write_force_map(tmp_path / "a.nid", 1_024, range(1, 1_024, 10))
    write_force_map(tmp_path / "b.NID", 256, retract=True)
    write_force_map(tmp_path / "c.nid", 16, range(16))
    (tmp_path / "d.nid").write_bytes(b"truncated")

    exports = []
    for parallel in (False, True):
        events = []
        result = process_force_folder(
            tmp_path,
            RECIPE,
            parallel=parallel,
            progress=lambda fraction, name, events=events: events.append((fraction, name)),
        )
        assert [row.source for row in result.rows] == ["a.nid", "b.NID", "c.nid", "d.nid"]
        assert (result.n_ok, result.n_failed) == (2, 2)
        assert (result.n_curves, result.n_curves_ok, result.n_curves_failed) == (1296, 1177, 119)
        assert [(row.n_curves, row.n_ok, row.n_young_modulus) for row in result.rows] == [
            (1024, 921, 921),
            (256, 256, 256),
            (16, 0, 0),
            (0, 0, 0),
        ]
        assert result.rows[0].young_modulus_median == pytest.approx(1e6, rel=0.1)
        assert [row.n_dissipation for row in result.rows] == [0, 256, 0, 0]
        assert "Curva 1:" in result.rows[2].error
        assert result.rows[3].error
        for row in result.rows:
            assert (
                row.source_sha256
                == hashlib.sha256((tmp_path / row.source).read_bytes()).hexdigest()
            )
        assert any(0 < fraction < 0.25 for fraction, _ in events)
        assert [f for f, _ in events] == sorted(f for f, _ in events)
        assert events[-1] == (1.0, "d.nid")

        out = tmp_path / "summary.csv"
        result.to_csv(out)
        exports.append(out.read_bytes())
        lines = out.read_text(encoding="utf-8").splitlines()
        assert any("1296" in line and "1177" in line and "119" in line for line in lines)
        rows = list(
            csv.DictReader(
                io.StringIO("\n".join(line for line in lines if not line.startswith("#")))
            )
        )
        assert rows[0]["n_curves_failed"] == "103"
        assert rows[2]["young_modulus_median [Pa]"] == ""
        assert rows[0]["dissipation_median [J]"] == ""
        assert float(rows[1]["dissipation_median [J]"]) > 0
    assert exports[0] == exports[1]


@pytest.mark.parametrize("parallel", [False, True])
def test_stops_inside_a_map_when_progress_requests_cancellation(
    tmp_path: Path, parallel: bool
) -> None:
    class Cancelled(Exception):
        pass

    write_force_map(tmp_path / "a.nid", 256)

    def progress(fraction: float, name: str) -> None:
        if 0 < fraction < 1:
            raise Cancelled(name)

    with pytest.raises(Cancelled, match="a.nid"):
        process_force_folder(tmp_path, RECIPE, parallel=parallel, progress=progress)


def test_non_numeric_context_does_not_invalidate_numeric_properties(tmp_path: Path) -> None:
    write_force_map(tmp_path / "a.nid", 1)
    result = process_force_folder(tmp_path, RECIPE, keys=("fit_axis", "fit", "young_modulus"))
    assert result.n_ok == 1
    assert result.rows[0].n_young_modulus == 1


def test_nid_keeps_only_matching_separation_and_trims_padding(tmp_path: Path) -> None:
    path = tmp_path / "paired.nid"
    write_force_map(path, 2, range(1))
    header, data = path.read_bytes().split(b"#!", 1)
    prefix, height_header = header.split(b"[Channel-1]", 1)
    datasets, force_header = prefix.split(b"[Channel-0]", 1)
    datasets = datasets.replace(b"Gr0-Count=2", b"Gr0-Count=4")
    datasets += b"Gr0-Ch2=Separation\nGr0-Ch3=PairedForce\n"
    separation_header = height_header.replace(b"Z-Axis Sensor", b"Tip-Sample Separation")
    separation_header = separation_header.replace(b"Spec forward", b"IndentationZSensorFwd")
    paired_header = force_header.replace(b"Spec forward", b"IndentationDeflFwd")
    force, height = data[: len(data) // 2], data[len(data) // 2 :]
    paired = np.frombuffer(force, dtype="<i4").copy()
    paired[-1] += 1
    path.write_bytes(
        datasets
        + b"[Channel-0]"
        + force_header
        + b"[Channel-1]"
        + height_header
        + b"[Separation]"
        + separation_header
        + b"[PairedForce]"
        + paired_header
        + b"#!"
        + data
        + height
        + paired.tobytes()
    )
    volume = load_nid_force(path)
    first, second = volume.curve(0).extend, volume.curve(1).extend
    assert first.metadata["separation_status"] == "matched"
    assert first.separation.size == 3
    assert second.metadata["separation_status"] == "force_mismatch"
    assert second.separation is None


def test_missing_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        process_force_folder(tmp_path / "missing", RECIPE)


def test_export_failure_preserves_existing_csv(tmp_path: Path) -> None:
    out = tmp_path / "summary.csv"
    out.write_bytes(b"previous export")
    result = ForceBatchResult(recipe={"unsupported_parameter": object()})
    with pytest.raises(TypeError):
        result.to_csv(out)
    assert out.read_bytes() == b"previous export"
    assert list(tmp_path.iterdir()) == [out]

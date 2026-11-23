"""Entirely generated mixed image/spectroscopy NID maps with known pull-off forces."""

import csv
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.adhesion_review import export_review, export_traces, review_maps


def write_adhesion_map(
    path: Path, n: int = 100, separation: bool = True, retract: bool = True
) -> None:
    points = 48
    z = np.tile(np.arange(points), (n, 1))
    f = np.zeros((n, points), dtype=int)
    for i in range(n):
        f[i] = 12 + i % 3
        if i != n - 1:
            f[i, 16:21] -= i + 1
        else:
            f[i, 18] -= i + 1
    channels = [
        ("Scan forward", "Z-Axis", "nm", np.arange(16).reshape(4, 4)),
        ("Spec forward", "Deflection", "nN", -z * 20),
        ("Spec forward", "Z-Axis Sensor", "nm", z[:, ::-1]),
    ]
    if retract:
        channels.extend(
            [("Spec backward", "Deflection", "nN", f), ("Spec backward", "Z-Axis Sensor", "nm", z)]
        )
    if separation:
        channels.extend(
            [
                ("IndentationZSensorFwd0", "Tip-Sample Separation", "nm", z[:, ::-1] * 2),
                ("IndentationDeflFwd0", "Deflection", "nN", -z * 20),
            ]
        )
        if retract:
            channels.extend(
                [
                    ("IndentationZSensorBwd0", "Tip-Sample Separation", "nm", z * 2),
                    ("IndentationDeflBwd0", "Deflection", "nN", f),
                ]
            )
    h = ["[DataSet]", "GroupCount=1", f"Gr0-Count={len(channels)}"]
    h.extend(f"Gr0-Ch{i}=Ch{i}" for i in range(len(channels)))
    payload = []
    for i, (frame, name, unit, data) in enumerate(channels):
        h.extend(
            [
                f"[Ch{i}]",
                f"Points={data.shape[1]}",
                f"Lines={data.shape[0]}",
                f"Frame={frame}",
                "Dim1Name=Y" if i == 0 else "Dim1Name=SpecPoint",
                f"Dim2Name={name}",
                f"Dim2Unit={unit}",
                "Dim2Min=-32768",
                "Dim2Range=65536",
                "SaveBits=16",
            ]
        )
        payload.append(data.astype("<i2").tobytes())
    path.write_bytes(("\n".join(h) + "\n#!").encode() + b"".join(payload))


def read_csv(p):
    with p.open() as f:
        return list(csv.DictReader(f))


def test_selection_all_curves_export_and_input_integrity(tmp_path):
    p = tmp_path / "A.nid"
    q = tmp_path / "B.nid"
    write_adhesion_map(p)
    write_adhesion_map(q, separation=False)
    missing = tmp_path / "missing.nid"
    maps, volume = review_maps([p, missing, q])
    assert maps[1].error and volume.n_curves == 100
    for m in (maps[0], maps[2]):
        assert m.shape == (10, 10)
        np.testing.assert_allclose(m.selected_values(), np.arange(1, 101) * 1e-9)
        assert [r.index for r in m.curves if r.warning] == [99]
    maps[0].curves[-1].included = False
    out = tmp_path / "res.csv"
    export_review(maps, out, summary=True)
    a, e, b = read_csv(out)
    assert a["n_selected"] == "99" and b["n_selected"] == "100" and e["error"]
    assert float(a["median_adhesion_n"]) == pytest.approx(50e-9)
    export_review(maps, out, summary=False)
    all_rows = read_csv(out)
    assert len(all_rows) == 201 and all_rows[99]["included"] == "False"
    assert float(all_rows[99]["adhesion_n"]) == pytest.approx(100e-9)
    export_traces(maps, out)
    samples = read_csv(out)
    assert len(samples) == 199 * 2 * 48
    assert samples[0]["separation_status"] == "matched" and samples[-1]["separation_m"] == ""
    assert not any(r["source"] == "A.nid" and r["curve"] == "99" for r in samples)
    prior = out.read_bytes()
    q.write_bytes(b"changed synthetic input")
    with pytest.raises(ValueError, match="cambió"):
        export_traces(maps, out)
    assert prior == out.read_bytes()


def test_missing_retract_preserves_each_curve_without_fabricating_adhesion(tmp_path):
    p = tmp_path / "extend.nid"
    write_adhesion_map(p, 3, retract=False)
    m = review_maps([p])[0][0]
    assert len(m.curves) == 3 and all(r.included and r.warning for r in m.curves)
    assert m.selected_values() == []

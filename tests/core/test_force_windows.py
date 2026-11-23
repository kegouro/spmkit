"""Synthetic-only acceptance tests for the two NID window selectors."""

import csv
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis.force_windows import WindowOptions, select_windows
from spmkit.core.force_window_batch import analyze_window_files
from spmkit.core.models import ForceCurve, ForceSegment


def curve(z, f, branch="extend"):
    s = ForceSegment(
        branch,
        "approach" if branch == "extend" else "retract",
        z,
        f,
        force=f,
        separation=z,
        state="force_n",
    )
    return ForceCurve((s,))


@pytest.mark.parametrize("direction", (1, -1))
@pytest.mark.parametrize("rho", (0, 0.65))
def test_local_steps_ignore_drift_single_spikes_and_null_controls(direction, rho):
    n = 640
    rng = np.random.default_rng(105)
    z = direction * np.arange(n) * 1e-9
    for i in range(24):
        noise = rng.normal(0, 0.02e-9, n)
        for j in range(1, n):
            noise[j] += rho * noise[j - 1]
        force = 0.025 * z + noise
        force[55] += 1e-9
        p, q = 130 + i, 450 - i
        if i % 2:
            force[p:] += 1.7e-9
            force[q:] -= 1.2e-9
        w = select_windows(curve(z, force, "retract"), WindowOptions("steps", "retract"))
        expected = [p, q] if i % 2 else []
        assert [r.boundary for r in w] == expected
        if w:
            np.testing.assert_allclose(
                [v.delta_force_n for v in w], [1.7e-9, -1.2e-9], atol=0.15e-9
            )
            assert w[0].start == p - 8 and w[0].end == p + 7


def write_map(path: Path, n: int, contact: bool):
    """Independent native int32 encoder, positive piezo travel, calibrated k=0.2 N/m."""
    cells = 640
    z = (np.arange(cells) - 260) * 0.25e-9
    rng = np.random.default_rng(129)
    forces = []
    heights = []
    for i in range(n):
        noise = rng.normal(0, 0.08e-12, cells)
        if contact:
            signal = 4 / 3 * 2.5e5 / (1 - 0.3**2) * np.sqrt(100e-9) * np.maximum(z, 0) ** 1.5
        else:
            signal = 0.01 * z + (np.arange(cells) >= 180 + i % 6) * 1.5e-9
        f = signal + noise + 2e-12
        forces.append(f)
        heights.append(z + f / 0.2 if contact else z)
    header = [
        "[DataSet]",
        "GroupCount=1",
        "Gr0-Count=2",
        "Gr0-Ch0=A",
        "Gr0-Ch1=B",
        r"[DataSet\Calibration\Cantilever]",
        "Prop0=D[0.2]*[N/m]",
    ]
    blocks = []
    for sec, name, unit, arr, gain in [
        ("A", "Deflection", "N", forces, 1e-16),
        ("B", "Z-Axis Sensor", "m", heights, 1e-15),
    ]:
        header.extend(
            [
                f"[{sec}]",
                f"Points={cells}",
                f"Lines={n}",
                "Dim1Name=SpecPoint",
                "Frame=Spec forward",
                f"Dim2Name={name}",
                f"Dim2Unit={unit}",
                f"Dim2Min={-2**31*gain}",
                f"Dim2Range={2**32*gain}",
            ]
        )
        blocks.append(np.rint(np.asarray(arr) / gain).astype("<i4").tobytes())
    path.write_bytes(("\n".join(header) + "\n#!").encode() + b"".join(blocks))


@pytest.mark.parametrize("mode", ("steps", "contact"))
def test_native_nid_multiple_maps_windows_and_csv(tmp_path, mode):
    files = [tmp_path / f"phantom-{i}.nid" for i in range(2)]
    for p in files:
        write_map(p, 64, mode == "contact")
    bad = tmp_path / "incomplete.nid"
    bad.write_bytes(b"[DataSet]")
    options = WindowOptions(mode, tip_radius_nm=100, max_depth_nm=12)
    progress = []
    out = analyze_window_files([bad, *files], options, lambda f, m: progress.append(f))
    assert progress == sorted(progress) and progress[-1] == 1
    assert out.rows[0].status == "error"
    assert len(out.rows) == 129
    for row in out.rows[1:]:
        w = row.window
        assert row.status == "candidato" and w and row.preview is not None
        if mode == "contact":
            assert abs(w.boundary - 260) <= 2
            assert w.modulus_pa == pytest.approx(2.5e5, rel=0.02)
            assert w.end < 315 and w.r_squared > 0.99
        else:
            assert w.boundary == 180 + row.curve % 6
            assert w.delta_force_n == pytest.approx(1.5e-9, rel=0.005)
    path = tmp_path / "out.csv"
    out.to_csv(path)
    with path.open() as s:
        records = list(csv.DictReader(s))
    assert len(records) == 129 and records[1]["mode"] == mode
    assert len(records[1]["sha256"]) == 64 and records[0]["modulus_pa"] == ""
    assert records[-1]["curve"] == "63"


def test_contact_refuses_flat_signal_and_missing_physical_axis():
    z = np.arange(400) * 1e-9
    o = WindowOptions("contact", tip_radius_nm=100, max_depth_nm=30)
    with pytest.raises(ValueError, match="contacto"):
        select_windows(curve(z, np.zeros_like(z)), o)
    f = np.maximum(z - z[160], 0) ** 1.5
    s = ForceSegment("extend", "approach", z, f, force=f, state="force_n")
    with pytest.raises(ValueError, match="separación"):
        select_windows(ForceCurve((s,)), o)


@pytest.mark.parametrize("direction", [-1, 1])
def test_shifted_contacts_holdout_and_controls(direction):
    rng = np.random.default_rng(20261124)
    base = np.arange(600) * 0.2e-9
    for _ in range(24):
        cp = int(rng.integers(125, 390))
        radius = rng.uniform(80, 200)
        modulus = rng.uniform(0.25e6, 2e6)
        delta = base - base[cp]
        force = (
            (4 / 3) * modulus / (1 - 0.3**2) * np.sqrt(radius * 1e-9) * np.maximum(delta, 0) ** 1.5
            + 1e-4 * base
            + rng.normal(0, 0.03e-12, len(base))
        )
        o = WindowOptions("contact", tip_radius_nm=radius, max_depth_nm=10)
        (win,) = select_windows(curve(direction * base, force), o)
        assert abs(win.boundary - cp) <= 2
        assert 0 < win.end - win.start <= 51
        assert win.modulus_pa == pytest.approx(modulus, rel=0.02)
        negative = 1e-4 * base + rng.normal(0, 0.03e-12, len(base))
        with pytest.raises(ValueError):
            select_windows(curve(direction * base, negative), o)


def test_window_export_protects_nid_and_previous_csv(tmp_path, monkeypatch):
    import os

    p = tmp_path / "phantom.nid"
    write_map(p, 2, False)
    original = p.read_bytes()
    out = analyze_window_files([p], WindowOptions("steps"))
    with pytest.raises(ValueError, match="csv"):
        out.to_csv(p)
    assert p.read_bytes() == original
    csv_path = tmp_path / "previous.csv"
    csv_path.write_text("previous result")

    def fail(*args):
        raise OSError("simulated final write failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        out.to_csv(csv_path)
    assert csv_path.read_text() == "previous result"


def test_ambiguous_plateau_is_not_a_hertz_fit():
    z = np.arange(640) * 0.25e-9
    # Repulsive crossing followed by a force plateau (adhesive/stepped response).
    f = (np.arange(len(z)) >= 180).astype(float) * 1e-9
    with pytest.raises(ValueError):
        select_windows(curve(z, f), WindowOptions("contact", tip_radius_nm=100, max_depth_nm=12))

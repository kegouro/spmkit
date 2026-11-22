import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from spmkit.cli.app import app
from spmkit.core.analysis.force_steps import measure_force_step
from spmkit.core.io.nid import load_nid_force
from spmkit.core.models import ForceSegment


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("jump", [-3e-9, 0.0, 2e-9])
def test_signed_jump_on_sloping_force(direction, jump):
    z = direction * np.arange(30) * 1e-9
    force = 0.4 * z
    force[15:] += jump
    segment = ForceSegment("extend", "approach", z, force, state="force_n", force=force)
    result = measure_force_step(segment, 15, 5)
    assert result.delta_force_n == pytest.approx(jump, abs=1e-22)
    assert result.height_m == pytest.approx((z[14] + z[15]) / 2, abs=1e-22)
    assert result.left_slope_n_per_m == pytest.approx(0.4)
    assert result.right_residual_rms_n < 1e-22


def write_spectrum(path: Path, unit: str) -> None:
    # Signed int16 with unit gain and zero offset. Two curves in acquisition order.
    header = ["[DataSet]", "GroupCount=1", "Gr0-Ch0=DataSet-0:0", "Gr0-Ch1=DataSet-0:1"]
    for i, (name, u) in enumerate([("Deflection", unit), ("Z-Axis Sensor", "nm")]):
        header.extend(
            [
                f"[DataSet-0:{i}]",
                "Points=12",
                "Lines=2",
                "Frame=Spec forward",
                "Dim1Name=SpecPoint",
                f"Dim2Name={name}",
                f"Dim2Unit={u}",
                "Dim2Min=-32768",
                "Dim2Range=65536",
                "SaveBits=16",
            ]
        )
    z = np.tile(np.arange(12, dtype="<i2"), (2, 1))
    f = z.copy()
    f[1, 6:] += 2
    path.write_bytes("\n".join(header).encode() + b"#!" + f.tobytes() + z.tobytes())


def test_cli_single_and_batch_share_measurements(tmp_path):
    source = tmp_path / "two.nid"
    write_spectrum(source, "nN")
    table = tmp_path / "annotations.csv"
    header = "source,curve,branch,cycle,boundary,window\n"
    selected = "two.nid,1,extend,0,6,4\n"
    table.write_text(header + selected)
    runner = CliRunner()
    single = runner.invoke(app, ["force-steps", str(table)])
    assert single.exit_code == 0, single.output
    first = json.loads(single.output)
    assert first["delta_force_n"] == pytest.approx(2e-9, abs=1e-22)
    assert first["height_m"] == pytest.approx(5.5e-9, abs=1e-22)
    trials = first["boundary_sensitivity"]
    assert [t["offset_samples"] for t in trials] == [-1, 1]
    np.testing.assert_allclose([t["delta_force_n"] for t in trials], 0.3e-9, rtol=1e-12, atol=0)
    assert first["height_channel"] == "Z-Axis Sensor"
    assert first["height_input_unit"] == "nm"
    assert first["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    table.write_text(header + selected + "two.nid,1,retract,0,6,4\ntwo.nid,0,extend,0,6,4\n")
    batch = runner.invoke(app, ["force-steps", str(table)])
    assert batch.exit_code == 1
    result = list(map(json.loads, batch.output.splitlines()))
    assert result[0] == first
    assert result[1]["status"] == "rejected"
    assert abs(result[2]["delta_force_n"]) < 1e-22


@pytest.mark.parametrize("unit", ["V", "", "nm"])
def test_incompatible_force_units_rejected(tmp_path, unit):
    path = tmp_path / "incompatible.nid"
    write_spectrum(path, unit)
    with pytest.raises(ValueError, match="unidad"):
        load_nid_force(path)


@pytest.mark.parametrize("rho", [0.0, 0.8])
def test_measurement_error_with_fixed_boundary(rho):
    # Independent OLS design-matrix prediction for stationary Gaussian AR(1) noise.
    rng = np.random.default_rng(20261122)
    n, sigma = 10, 0.1e-9
    x = np.arange(2 * n) - n + 0.5
    z = x * 1e-9
    weights = []
    for side in (x[:n], x[n:]):
        weights.append(np.linalg.pinv(np.column_stack([np.ones(n), side]))[0])
    contrast = np.r_[-weights[0], weights[1]]
    covariance = sigma**2 * rho ** np.abs(x[:, None] - x)
    predicted_sd = np.sqrt(contrast @ covariance @ contrast)
    errors = []
    for _ in range(512):
        noise = rng.normal(0, sigma, 2 * n)
        for j in range(1, 2 * n):
            noise[j] = rho * noise[j - 1] + np.sqrt(1 - rho**2) * noise[j]
        force = 0.4 * z + noise + (x > 0) * 2e-9
        seg = ForceSegment("extend", "approach", z, force, state="force_n", force=force)
        errors.append(measure_force_step(seg, n, n).delta_force_n - 2e-9)
    assert abs(np.mean(errors)) < 4 * predicted_sd / np.sqrt(len(errors))
    assert np.std(errors, ddof=1) == pytest.approx(predicted_sd, rel=0.12)


def test_batch_reports_denominators_for_each_property(tmp_path):
    from spmkit.core.forcebatch import process_force_folder
    from tests.core.test_forcebatch import _RECIPE, _make_jpk_force

    _make_jpk_force(tmp_path / "single.jpk-force")
    batch = process_force_folder(tmp_path, _RECIPE)
    row = batch.rows[0]
    assert row.n_curves == row.n_ok == row.n_young_modulus == 1
    assert row.n_dissipation == 0
    csv_path = tmp_path / "results.csv"
    batch.to_csv(csv_path)
    text = csv_path.read_text()
    assert hashlib.sha256((tmp_path / "single.jpk-force").read_bytes()).hexdigest() in text
    metadata = next(line[2:] for line in text.splitlines() if line.startswith("# {"))
    assert json.loads(metadata)["recipe"] == _RECIPE.to_dict()


@pytest.mark.parametrize("bad", ["window", "boundary", "reversal", "duplicate", "nan", "state"])
def test_step_rejects_unusable_annotation(bad):
    z = np.arange(12, dtype=float) * 1e-9
    f = np.ones_like(z)
    if bad == "reversal":
        z[6] = z[4]
    if bad == "duplicate":
        z[6] = z[5]
    if bad == "nan":
        f[5] = np.nan
    seg = ForceSegment(
        "retract", "retract", z, f, state="raw_v" if bad == "state" else "force_n", force=f
    )
    with pytest.raises(ValueError):
        measure_force_step(seg, 1 if bad == "boundary" else 6, 2 if bad == "window" else 4)


def test_jpk_step_reports_applied_height_slot(tmp_path):
    from tests.core.test_cli_force import _make_jpk_force

    _make_jpk_force(tmp_path / "single.jpk-force")
    table = tmp_path / "annotations.csv"
    table.write_text(
        "source,curve,branch,cycle,boundary,window\nsingle.jpk-force,0,extend,0,100,4\n"
    )
    result = CliRunner().invoke(app, ["force-steps", str(table)])
    assert result.exit_code == 0, result.output
    record = json.loads(result.output)
    assert record["height_channel"] == "height"
    assert record["height_conversion_slots"] == ["calibrated"]


def test_boundary_sensitivity_retains_valid_central_fit_at_edge(tmp_path):
    write_spectrum(tmp_path / "two.nid", "nN")
    table = tmp_path / "annotations.csv"
    table.write_text("source,curve,branch,cycle,boundary,window\ntwo.nid,1,extend,0,4,4\n")
    result = CliRunner().invoke(app, ["force-steps", str(table)])
    assert result.exit_code == 0, result.output
    record = json.loads(result.output)
    assert record["status"] == "measured"
    left, right = record["boundary_sensitivity"]
    assert left["offset_samples"] == -1 and "reason" in left
    assert right["offset_samples"] == 1 and "delta_force_n" in right

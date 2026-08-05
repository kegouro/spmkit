from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from spmkit import load
from spmkit.core.analysis import kpfm, leveling, profiles, roughness
from spmkit.core.export import to_csv, to_json
from spmkit.core.viz import FigureSpec, save_figure


def test_real_gwy_library_image_journey(real_gwy_path: Path, tmp_path: Path) -> None:
    data = load(real_gwy_path)

    assert data.metadata["format"] == "gwy"
    assert data.source_path == str(real_gwy_path)
    assert len(data.channels) == 3
    assert data.names == ["Z-Axis", "Z-Axis", "CPD"]
    forward = data.select("Z-Axis", direction="forward", group="Z-Axis forward")
    backward = data.select("Z-Axis", direction="backward", group="Z-Axis backward")
    assert forward.shape == backward.shape == (5, 7)
    assert forward.unit == backward.unit == "m"
    assert forward.x_range == backward.x_range == pytest.approx(7e-6)
    assert forward.y_range == backward.y_range == pytest.approx(10e-6)
    assert not np.array_equal(forward.data, backward.data)

    raw = forward.data.copy()
    leveled = leveling.plane_fit(forward)
    np.testing.assert_array_equal(forward.data, raw)
    assert not np.shares_memory(leveled.data, forward.data)

    roughness_result = roughness.statistics(leveled)
    assert roughness_result.unit == "m"
    assert all(
        np.isfinite(value)
        for value in (
            roughness_result.Sa,
            roughness_result.Sq,
            roughness_result.Sz,
            roughness_result.Sp,
            roughness_result.Sv,
            roughness_result.Ssk,
            roughness_result.Sku,
        )
    )

    profile = profiles.line(forward, (0.5, 0.5), (5.5, 3.5), n=3)
    assert profile.unit == "m"
    assert profile.distance_unit == "m"
    assert len(profile) == 3
    assert profile.height[0] == pytest.approx(float(np.mean(raw[:2, :2])))
    assert profile.height[1] == pytest.approx(float(raw[2, 3]))
    assert profile.height[-1] == pytest.approx(float(np.mean(raw[3:5, 5:7])))
    expected_distance = np.hypot(5.0 * forward.pixel_size_x, 3.0 * forward.pixel_size_y)
    assert profile.distance[-1] == pytest.approx(expected_distance)

    cpd_channel = data.select("CPD", direction="forward", group="CPD forward")
    assert cpd_channel.shape == (5, 7)
    assert cpd_channel.unit == "V"
    cpd_result = kpfm.statistics(cpd_channel, tip_work_function=4.7)
    assert cpd_result.mean == pytest.approx(0.135)
    assert cpd_result.minimum == pytest.approx(0.1)
    assert cpd_result.maximum == pytest.approx(0.17)
    assert cpd_result.contrast == pytest.approx(0.07)
    assert cpd_result.work_function == pytest.approx(4.7 - cpd_result.mean)
    assert cpd_result.work_function_unit == "eV"

    roughness_csv = to_csv(roughness_result, tmp_path / "roughness.csv")
    with roughness_csv.open(newline="", encoding="utf-8") as stream:
        roughness_rows = {row["key"]: row["value"] for row in csv.DictReader(stream)}
    assert roughness_rows["unit"] == roughness_result.unit
    assert float(roughness_rows["Sq"]) == pytest.approx(roughness_result.Sq)
    assert int(roughness_rows["n_points"]) == roughness_result.n_points

    profile_csv = to_csv(profile, tmp_path / "profile.csv")
    with profile_csv.open(newline="", encoding="utf-8") as stream:
        profile_rows = list(csv.DictReader(stream))
    assert tuple(profile_rows[0]) == ("distance[m]", "height[m]")
    np.testing.assert_allclose(
        [float(row["distance[m]"]) for row in profile_rows], profile.distance
    )
    np.testing.assert_allclose([float(row["height[m]"]) for row in profile_rows], profile.height)

    kpfm_json = to_json(cpd_result, tmp_path / "kpfm.json")
    reopened_kpfm = json.loads(kpfm_json.read_text(encoding="utf-8"))
    assert reopened_kpfm["unit"] == cpd_result.unit
    assert reopened_kpfm["work_function_unit"] == cpd_result.work_function_unit
    assert reopened_kpfm["mean"] == pytest.approx(cpd_result.mean)
    assert reopened_kpfm["work_function"] == pytest.approx(cpd_result.work_function)

    figure_path = save_figure(forward, FigureSpec(), tmp_path / "topography.png")
    figure_bytes = figure_path.read_bytes()
    assert figure_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(figure_bytes) > 1_000

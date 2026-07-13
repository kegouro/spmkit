"""Tests de exportación."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import profiles, roughness
from spmkit.core.export import to_csv, to_json
from spmkit.core.models import SPMChannel, SPMData


def test_roughness_to_json(flat_noisy: SPMChannel, tmp_path: Path) -> None:
    r = roughness.statistics(flat_noisy)
    out = to_json(r, tmp_path / "r.json")
    loaded = json.loads(out.read_text())
    assert loaded["Sq"] == r.Sq
    assert loaded["unit"] == "m"


def test_roughness_to_csv(flat_noisy: SPMChannel, tmp_path: Path) -> None:
    r = roughness.statistics(flat_noisy)
    out = to_csv(r, tmp_path / "r.csv")
    text = out.read_text()
    assert "key,value" in text
    assert "Sq" in text


def test_roughness_round_trip_csv_json(tmp_path: Path) -> None:
    channel = SPMChannel(
        name="Z",
        data=np.array([[1.0, 2.0], [3.0, 4.0]]),
        unit="m",
        x_range=1.0,
        y_range=1.0,
    )
    result = roughness.statistics(channel)

    csv_path = to_csv(result, tmp_path / "roughness.csv")
    json_path = to_json(result, tmp_path / "roughness.json")

    with csv_path.open(newline="") as file:
        csv_result = {row["key"]: row["value"] for row in csv.DictReader(file)}
    json_result = json.loads(json_path.read_text())

    assert float(csv_result["Sa"]) == result.Sa
    assert float(csv_result["Sq"]) == result.Sq
    assert csv_result["unit"] == result.unit
    assert int(csv_result["n_points"]) == result.n_points
    assert json_result["Sa"] == result.Sa
    assert json_result["Sq"] == result.Sq
    assert json_result["unit"] == result.unit
    assert json_result["n_points"] == result.n_points


def test_profile_to_csv(tmp_path: Path) -> None:
    ch = SPMChannel(name="Z", data=np.zeros((5, 5)), unit="m", x_range=1e-6, y_range=1e-6)
    prof = profiles.line(ch, (0, 0), (4, 0), n=5)
    out = to_csv(prof, tmp_path / "p.csv")
    lines = out.read_text().splitlines()
    assert lines[0].startswith("distance")
    assert len(lines) == 6  # cabecera + 5 puntos


def test_json_handles_ndarray(tmp_path: Path) -> None:
    data = SPMData(channels=(), metadata={"arr": np.array([1, 2, 3])})
    out = to_json(data.metadata, tmp_path / "m.json")
    assert json.loads(out.read_text())["arr"] == [1, 2, 3]

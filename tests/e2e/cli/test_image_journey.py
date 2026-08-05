from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from spmkit import load
from spmkit.cli.app import app
from spmkit.core.analysis import kpfm, leveling, roughness

runner = CliRunner()


def _compact_output(output: str) -> str:
    return "".join(unstyle(output).replace("│", " ").split())


def _csv_scalars(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as stream:
        return {row["key"]: row["value"] for row in csv.DictReader(stream)}


def test_real_gwy_cli_info_selection_and_analysis(real_gwy_path: Path, tmp_path: Path) -> None:
    info_result = runner.invoke(app, ["info", str(real_gwy_path)], terminal_width=200)
    assert info_result.exit_code == 0, info_result.output
    info_output = _compact_output(info_result.output)
    assert "formatogwy" in info_output
    assert "Grupo" in info_output
    assert "Z-Axisforward" in info_output
    assert "Z-Axisbackward" in info_output
    assert "CPDforward" in info_output

    roughness_result = runner.invoke(
        app,
        ["roughness", str(real_gwy_path), "--direction", "forward", "--level", "plane"],
    )
    assert roughness_result.exit_code == 0, roughness_result.output

    ambiguous_result = runner.invoke(app, ["roughness", str(real_gwy_path)])
    assert ambiguous_result.exit_code == 2
    normalized_error = _compact_output(ambiguous_result.output)
    assert "ambigua" in normalized_error.casefold()
    assert "--direction/--group" in normalized_error

    output_dir = tmp_path / "analysis"
    analyze_result = runner.invoke(
        app,
        [
            "analyze",
            str(real_gwy_path),
            "--output",
            str(output_dir),
            "--direction",
            "forward",
            "--cpd-direction",
            "forward",
            "--tip-wf",
            "4.7",
        ],
    )
    assert analyze_result.exit_code == 0, analyze_result.output

    data = load(real_gwy_path)
    expected_roughness = roughness.statistics(
        leveling.plane_fit(data.select("Z-Axis", direction="forward"))
    )
    expected_kpfm = kpfm.statistics(data.select("CPD", direction="forward"), tip_work_function=4.7)
    stem = real_gwy_path.stem
    roughness_csv = _csv_scalars(output_dir / f"{stem}_roughness.csv")
    roughness_json = json.loads((output_dir / f"{stem}_roughness.json").read_text(encoding="utf-8"))
    kpfm_csv = _csv_scalars(output_dir / f"{stem}_kpfm.csv")
    kpfm_json = json.loads((output_dir / f"{stem}_kpfm.json").read_text(encoding="utf-8"))
    assert roughness_csv["unit"] == roughness_json["unit"] == expected_roughness.unit
    assert float(roughness_csv["Sq"]) == pytest.approx(expected_roughness.Sq)
    assert roughness_json["Sq"] == pytest.approx(expected_roughness.Sq)
    assert kpfm_csv["unit"] == kpfm_json["unit"] == expected_kpfm.unit
    assert float(kpfm_csv["mean"]) == pytest.approx(expected_kpfm.mean)
    assert kpfm_json["work_function"] == pytest.approx(expected_kpfm.work_function)


def test_real_gwy_cli_profile_and_default_figure(real_gwy_path: Path, tmp_path: Path) -> None:
    profile_help = runner.invoke(app, ["profile", "--help"])
    assert profile_help.exit_code == 0, profile_help.output
    profile_output = _compact_output(profile_help.output)
    assert "coordenadasdepíxel" in profile_output
    assert "--x1" in profile_output and "required" in profile_output
    assert "--y1" in profile_output and "required" in profile_output

    profile_path = tmp_path / "profile.csv"
    profile_result = runner.invoke(
        app,
        [
            "profile",
            str(real_gwy_path),
            "--direction",
            "forward",
            "--x0",
            "0.5",
            "--y0",
            "0.5",
            "--x1",
            "5.5",
            "--y1",
            "3.5",
            "--n",
            "3",
            "--level",
            "none",
            "--output",
            str(profile_path),
        ],
    )
    assert profile_result.exit_code == 0, profile_result.output
    with profile_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == ["distance[m]", "height[m]"]
    assert len(rows) == 4
    for row in rows[1:]:
        assert len(row) == 2
        assert all(math.isfinite(float(value)) for value in row)

    invalid_profile = runner.invoke(
        app,
        [
            "profile",
            str(real_gwy_path),
            "--direction",
            "forward",
            "--x1",
            "7",
            "--y1",
            "4",
        ],
    )
    assert invalid_profile.exit_code == 2
    assert "fueradeloslímites" in _compact_output(invalid_profile.output)

    figure_help = runner.invoke(app, ["figure", "--help"])
    assert figure_help.exit_code == 0, figure_help.output
    assert "gold" in figure_help.output
    figure_path = tmp_path / "figure.png"
    figure_result = runner.invoke(
        app,
        [
            "figure",
            str(real_gwy_path),
            "--direction",
            "forward",
            "--output",
            str(figure_path),
        ],
    )
    assert figure_result.exit_code == 0, figure_result.output
    figure_bytes = figure_path.read_bytes()
    assert figure_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(figure_bytes) > 1_000

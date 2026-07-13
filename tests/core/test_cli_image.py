from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from spmkit.core.models import SPMChannel, SPMData

cli_app = importlib.import_module("spmkit.cli.app")
app = cli_app.app
runner = CliRunner()


def _channel(
    direction: str = "forward",
    group: str = "Scan 1",
    *,
    name: str = "Z-Axis",
    values: np.ndarray | None = None,
) -> SPMChannel:
    return SPMChannel(
        name=name,
        data=np.asarray(values if values is not None else np.arange(9).reshape(3, 3)),
        unit="m" if name == "Z-Axis" else "V",
        x_range=1e-6,
        y_range=1e-6,
        direction=direction,
        group=group,
    )


def _invoke_roughness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    data: SPMData,
    *args: str,
) -> tuple[Any, list[SPMChannel]]:
    source = tmp_path / "synthetic.gwy"
    source.touch()
    selected: list[SPMChannel] = []
    monkeypatch.setattr(cli_app, "load", lambda _path: data)

    def fake_statistics(channel: SPMChannel) -> SimpleNamespace:
        selected.append(channel)
        return SimpleNamespace(unit=channel.unit, to_dict=lambda: {"Sa": 0.0})

    monkeypatch.setattr(cli_app.roughness, "statistics", fake_statistics)
    result = runner.invoke(app, ["roughness", str(source), *args], terminal_width=200)
    return result, selected


@pytest.mark.parametrize("command", ["roughness", "analyze", "psd", "figure"])
def test_help_canales_incluye_selectores_y_gwy(command: str) -> None:
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0, result.output
    assert "--direction" in result.output
    assert "--group" in result.output
    assert ".gwy" in result.output


def test_help_level_muestra_choices_y_analyze_muestra_selectores_cpd() -> None:
    roughness_help = runner.invoke(app, ["roughness", "--help"])
    analyze_help = runner.invoke(app, ["analyze", "--help"])

    assert roughness_help.exit_code == 0, roughness_help.output
    assert all(choice in roughness_help.output for choice in ("plane", "poly", "rows", "none"))
    assert "--cpd-direction" in analyze_help.output
    assert "--cpd-group" in analyze_help.output


def test_info_muestra_grupo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "synthetic.gwy"
    source.touch()
    monkeypatch.setattr(cli_app, "load", lambda _path: SPMData(channels=(_channel(),)))

    result = runner.invoke(app, ["info", str(source)])

    assert result.exit_code == 0, result.output
    assert "Grupo" in result.output
    assert "Scan 1" in result.output


def test_level_invalido_se_rechaza_durante_parsing_con_choices(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.gwy"
    source.touch()

    result = runner.invoke(app, ["roughness", str(source), "--level", "invalid"])

    assert result.exit_code == 2
    assert "invalid" in result.output
    assert all(choice in result.output for choice in ("plane", "poly", "rows", "none"))


def test_roughness_rows_usa_mediana(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    raw = np.array([[1.0, 2.0, 100.0], [10.0, 20.0, 30.0], [5.0, 5.0, 9.0]])
    data = SPMData(channels=(_channel(values=raw),))

    result, selected = _invoke_roughness(monkeypatch, tmp_path, data, "--level", "rows")

    assert result.exit_code == 0, result.output
    np.testing.assert_allclose(np.median(selected[0].data, axis=1), 0.0)


def test_roughness_selecciona_canal_exacto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    channels = (
        _channel("forward", "Scan 1"),
        _channel("forward", "Scan 2"),
        _channel("backward", "Scan 1"),
    )

    result, selected = _invoke_roughness(
        monkeypatch,
        tmp_path,
        SPMData(channels=channels),
        "--direction",
        "forward",
        "--group",
        "Scan 2",
        "--level",
        "none",
    )

    assert result.exit_code == 0, result.output
    assert selected == [channels[1]]


def test_roughness_ambigua_es_bad_parameter_accionable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = SPMData(channels=(_channel(group="Scan 1"), _channel(group="Scan 2")))

    result, selected = _invoke_roughness(monkeypatch, tmp_path, data)

    assert result.exit_code == 2
    normalized_output = " ".join(result.output.replace("│", " ").split())
    assert "ambigua" in normalized_output
    assert "Scan 1" in normalized_output
    assert "Scan 2" in normalized_output
    assert "--direction" in normalized_output
    assert "--group" in normalized_output
    assert selected == []


def test_roughness_ausente_incluye_opciones_disponibles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = SPMData(channels=(_channel(name="Height", group="Topography"),))

    result, selected = _invoke_roughness(monkeypatch, tmp_path, data)

    assert result.exit_code == 2
    assert "Disponibles" in result.output
    assert "Height" in result.output
    assert "Topography" in result.output
    assert selected == []


def test_analyze_omite_cpd_solo_si_el_nombre_no_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "synthetic.gwy"
    source.touch()
    data = SPMData(channels=(_channel(),))
    monkeypatch.setattr(cli_app, "load", lambda _path: data)
    monkeypatch.setattr(
        cli_app.roughness,
        "statistics",
        lambda channel: SimpleNamespace(unit=channel.unit, to_dict=lambda: {"Sa": 0.0}),
    )
    monkeypatch.setattr(cli_app, "to_csv", lambda *_args: None)
    monkeypatch.setattr(cli_app, "to_json", lambda *_args: None)

    result = runner.invoke(
        app, ["analyze", str(source), "--output", str(tmp_path / "output"), "--level", "none"]
    )

    assert result.exit_code == 0, result.output
    assert "Sin canal CPD" in result.output


def test_analyze_rechaza_cpd_ambiguo_si_el_nombre_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "synthetic.gwy"
    source.touch()
    data = SPMData(
        channels=(
            _channel(),
            _channel(name="CPD", group="Scan 1"),
            _channel(name="CPD", group="Scan 2"),
        )
    )
    monkeypatch.setattr(cli_app, "load", lambda _path: data)
    monkeypatch.setattr(
        cli_app.roughness,
        "statistics",
        lambda channel: SimpleNamespace(unit=channel.unit, to_dict=lambda: {"Sa": 0.0}),
    )
    monkeypatch.setattr(cli_app, "to_csv", lambda *_args: None)
    monkeypatch.setattr(cli_app, "to_json", lambda *_args: None)

    result = runner.invoke(
        app, ["analyze", str(source), "--output", str(tmp_path / "output"), "--level", "none"]
    )

    assert result.exit_code == 2
    assert "ambigua" in result.output
    assert "Scan 1" in result.output
    assert "Scan 2" in result.output
    assert "--cpd-direction" in result.output
    assert "--cpd-group" in result.output

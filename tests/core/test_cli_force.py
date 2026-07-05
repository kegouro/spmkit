"""Tests de los comandos CLI de curvas de fuerza (forcecurve/forcemap/fbatch)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from spmkit.cli.app import app

runner = CliRunner()


def _make_jpk_force(path: Path) -> None:
    n = 400
    sep = np.linspace(6e-7, 0.0, n)
    e_star = 1.0e6 / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    force_n = k * np.clip(3e-7 - sep, 0.0, None) ** 1.5
    raw_h = np.round(sep / 1e-9).astype(">i2")
    raw_vd = np.round(force_n / 1e-12).astype(">i2")
    header = "\n".join(
        [
            "force-segment-header.name.name=extend-spm",
            "channel.height.data.type=short",
            "channel.height.data.encoder.scaling.multiplier=1.0E-9",
            "channel.height.data.encoder.scaling.offset=0.0",
            "channel.height.conversion-set.conversions.list=calibrated",
            "channel.height.conversion-set.conversion.calibrated.scaling.multiplier=1.0",
            "channel.height.conversion-set.conversion.calibrated.scaling.offset=0.0",
            "channel.vDeflection.data.type=short",
            "channel.vDeflection.data.encoder.scaling.multiplier=1.0",
            "channel.vDeflection.data.encoder.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversions.list=distance force",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.multiplier=1.0E-6",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversion.force.scaling.multiplier=1.0E-6",
            "channel.vDeflection.conversion-set.conversion.force.scaling.offset=0.0",
        ]
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("header.properties", "jpk-data-file=spm-forcefile\n")
        zf.writestr("segments/0/segment-header.properties", header)
        zf.writestr("segments/0/channels/height.dat", raw_h.tobytes())
        zf.writestr("segments/0/channels/vDeflection.dat", raw_vd.tobytes())


def test_forcecurve_command(tmp_path: Path) -> None:
    jpk = tmp_path / "c.jpk-force"
    _make_jpk_force(jpk)
    result = runner.invoke(app, ["forcecurve", str(jpk)])
    assert result.exit_code == 0, result.output
    assert "Módulo de Young" in result.output


def test_forcecurve_out_of_range(tmp_path: Path) -> None:
    jpk = tmp_path / "c.jpk-force"
    _make_jpk_force(jpk)
    result = runner.invoke(app, ["forcecurve", str(jpk), "--curve", "99"])
    assert result.exit_code == 1
    assert "fuera de rango" in result.output


def test_fbatch_command(tmp_path: Path) -> None:
    for i in range(2):
        _make_jpk_force(tmp_path / f"c{i}.jpk-force")
    out = tmp_path / "resumen.csv"
    result = runner.invoke(app, ["fbatch", str(tmp_path), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "2 archivos" in result.output

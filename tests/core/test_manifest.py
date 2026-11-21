"""Portable provenance integration tests with synthetic instrument bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from spmkit.cli.app import app
from spmkit.core.export.manifest import RunManifest


def test_cli_manifest(nid_file: Path, tmp_path: Path) -> None:
    output = tmp_path / "results"
    result = CliRunner().invoke(app, ["analyze", str(nid_file), "--output", str(output)])
    assert result.exit_code == 0, result.output
    manifest = json.loads((output / f"{nid_file.stem}_run_manifest.json").read_text())
    assert manifest["schema_version"] == "1.0"
    assert manifest["input_file"] == nid_file.name
    assert manifest["input_sha256"] == hashlib.sha256(nid_file.read_bytes()).hexdigest()
    assert manifest["input_bytes"] == nid_file.stat().st_size
    assert manifest["results_produced"] == ["roughness"]
    assert manifest["warnings"]
    assert manifest["units"] == "m"
    assert manifest["status"] == "OK"
    for suffix in ("csv", "json"):
        assert (output / f"{nid_file.stem}_roughness.{suffix}").is_file()


def test_manifest_numpy_json(nid_file: Path) -> None:
    manifest = RunManifest.create(
        input_path=nid_file,
        command="test",
        args={"count": np.int64(2), "nested": [np.array([1, 2])]},
        channel="Z-Axis",
        leveling_method="none",
        units="m",
        results_produced=[],
        warnings=[],
        status="OK",
        duration_seconds=0.0,
    )
    assert json.loads(json.dumps(manifest.to_dict()))["args"] == {"count": 2, "nested": [[1, 2]]}

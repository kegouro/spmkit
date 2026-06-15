"""Tests de visualización, reporte y procesamiento por lotes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import roughness
from spmkit.core.batch import process
from spmkit.core.models import SPMChannel
from spmkit.core.viz import colormaps


def _channel() -> SPMChannel:
    return SPMChannel(
        name="Z-Axis",
        data=np.random.default_rng(0).normal(size=(32, 32)),
        unit="m",
        x_range=5e-6,
        y_range=5e-6,
    )


def test_colormaps_available() -> None:
    names = colormaps.available()
    assert "batlow" in names or "viridis" in names


def test_get_cmap_fallback() -> None:
    pytest.importorskip("matplotlib")
    cmap = colormaps.get_cmap("definitivamente-no-existe")
    assert cmap is not None  # cae a viridis sin reventar


def test_save_figure_png(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from spmkit.core.viz import FigureSpec, save_figure

    out = save_figure(_channel(), FigureSpec(title="Test"), tmp_path / "fig.png")
    assert out.exists() and out.stat().st_size > 0


def test_build_report(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("jinja2")
    from spmkit.core.models import SPMData
    from spmkit.core.report import build_report

    ch = _channel()
    data = SPMData(channels=(ch,), source_path="test.nid")
    out = build_report(data, ch, {"Rugosidad": roughness.statistics(ch)}, tmp_path / "r.html")
    html = out.read_text()
    assert "Reporte de análisis SPM" in html
    assert "data:image/png;base64," in html


def test_batch_process(tmp_path: Path, nid_file: Path) -> None:
    # Copia el .nid sintético a una carpeta y procesa el lote.
    folder = tmp_path / "batch"
    folder.mkdir()
    (folder / "a.nid").write_bytes(nid_file.read_bytes())
    (folder / "b.nid").write_bytes(nid_file.read_bytes())
    result = process([folder / "a.nid", folder / "b.nid"])
    assert result.n_ok == 2
    assert result.rows[0].Sq is not None
    csv_out = result.to_csv(tmp_path / "summary.csv")
    assert "Sq" in csv_out.read_text()


def test_batch_handles_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.nid"
    bad.write_bytes(b"not a real nid")
    result = process([bad])
    assert result.n_failed == 1
    assert result.rows[0].error

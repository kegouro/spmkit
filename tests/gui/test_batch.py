"""Tests del batch: VM sobre carpeta y render de la tabla."""

from __future__ import annotations

from pathlib import Path

import pytest

from spmkit.core.forcebatch import ForceBatchResult, ForceBatchRow
from spmkit.gui.panels.batch_table import BatchTablePanel, _fmt
from spmkit.gui.viewmodels import BatchViewModel, ForceViewModel

_JPK_DIR = Path(__file__).resolve().parents[2] / "reference" / "jpk_samples"


def test_batch_vm_empty_folder(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    bvm = BatchViewModel(ForceViewModel())
    seen = []
    bvm.batchReady.connect(seen.append)
    bvm.run_now(tmp_path)
    assert isinstance(bvm.result, ForceBatchResult)
    assert bvm.result.rows == []
    assert seen and seen[-1] is bvm.result


def test_batch_table_renders_rows(qtbot) -> None:  # type: ignore[no-untyped-def]
    bvm = BatchViewModel(ForceViewModel())
    panel = BatchTablePanel(bvm)
    qtbot.addWidget(panel)
    assert not panel.errored
    result = ForceBatchResult(
        rows=[
            ForceBatchRow(source="a.nid", n_curves=100, n_ok=98, young_modulus_median=5.0e5),
            ForceBatchRow(source="b.jpk-force", error="ilegible"),
        ]
    )
    panel._on_batch_ready(result)
    assert panel._model.rowCount() == 2
    assert panel._model.item(0, 0).text() == "a.nid"
    assert panel._model.item(0, 3).text() == "500"  # 5e5 Pa → 500 kPa
    assert panel._export_btn.isEnabled()


def test_fmt_handles_nan() -> None:
    assert _fmt(float("nan"), 1e-3) == "—"
    assert _fmt(2500.0, 1e-3) == "2.5"


@pytest.mark.skipif(not _JPK_DIR.exists(), reason="muestras JPK no disponibles (gitignored)")
def test_batch_processes_real_folder(qtbot) -> None:  # type: ignore[no-untyped-def]
    bvm = BatchViewModel(ForceViewModel())
    bvm.run_now(_JPK_DIR)
    assert bvm.result is not None
    assert len(bvm.result.rows) >= 1

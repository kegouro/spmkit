"""Robustez del parser: carga masiva de archivos reales y manejo de corrupción."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io import load_nid

_SAMPLES = Path(__file__).parents[2] / "reference" / "sample_files"
_NID_FILES = sorted(_SAMPLES.glob("**/*.nid")) if _SAMPLES.exists() else []


@pytest.mark.skipif(not _NID_FILES, reason="sin archivos .nid reales en reference/")
@pytest.mark.parametrize("path", _NID_FILES, ids=lambda p: p.name)
def test_real_nid_loads_with_finite_data(path: Path) -> None:
    data = load_nid(path)
    assert len(data) > 0
    for ch in data.channels:
        assert np.isfinite(ch.data).all(), f"datos no finitos en {ch.name}"
        assert ch.data.ndim == 2


def test_truncated_file_raises_clear_error(tmp_path: Path) -> None:
    # Header válido que declara 256x256 pero sin datos binarios suficientes.
    header = (
        "[DataSet]\r\nVersion=2\r\nGroupCount=1\r\nGr0-Count=1\r\n"
        "Gr0-Ch0=DataSet-0:0\r\n\r\n[DataSet-0:0]\r\nPoints=256\r\nLines=256\r\n"
        "Dim2Name=Z-Axis\r\nDim2Unit=m\r\nDim2Range=1\r\nDim2Min=0\r\n"
        "SaveBits=32\r\nSaveSign=Signed\r\nSaveOrder=Intel\r\n"
    )
    bad = tmp_path / "truncated.nid"
    bad.write_bytes(header.encode("latin-1") + b"#!" + b"\x00" * 100)  # faltan datos
    with pytest.raises(ValueError, match="truncado|corrupto"):
        load_nid(bad)

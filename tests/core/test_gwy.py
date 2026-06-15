"""Tests de interop .gwy (Gwyddion). Se omiten si gwyfile no está instalado."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.models import SPMChannel, SPMData

gwyfile = pytest.importorskip("gwyfile")

from spmkit.core.io import load, load_gwy, save_gwy  # noqa: E402


def _sample() -> SPMData:
    ch1 = SPMChannel(
        name="Z-Axis",
        data=np.arange(64.0).reshape(8, 8),
        unit="m",
        x_range=5e-6,
        y_range=5e-6,
        direction="forward",
    )
    ch2 = SPMChannel(
        name="Z-Axis",
        data=np.ones((8, 8)),
        unit="m",
        x_range=5e-6,
        y_range=5e-6,
        direction="backward",
    )
    return SPMData(channels=(ch1, ch2))


def test_gwy_roundtrip(tmp_path: Path) -> None:
    data = _sample()
    out = save_gwy(data, tmp_path / "out.gwy")
    reloaded = load_gwy(out)
    assert len(reloaded) == 2
    z = reloaded.get("Z-Axis", "forward")
    assert np.allclose(z.data, data["Z-Axis"].data)
    assert z.unit == "m"
    assert z.x_range == pytest.approx(5e-6)


def test_gwy_unique_titles(tmp_path: Path) -> None:
    # Dos canales con mismo nombre y dirección no deben colapsarse.
    ch = SPMChannel(name="Amp", data=np.zeros((4, 4)), unit="V", x_range=1e-6, y_range=1e-6)
    data = SPMData(channels=(ch, ch))
    reloaded = load_gwy(save_gwy(data, tmp_path / "dup.gwy"))
    assert len(reloaded) == 2


def test_gwy_dispatch(tmp_path: Path) -> None:
    out = save_gwy(_sample(), tmp_path / "d.gwy")
    assert load(out).metadata["format"] == "gwy"

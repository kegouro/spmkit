"""Tests del dispatcher load_force (curva/volumen por extensión → ForceVolume)."""

from __future__ import annotations

from pathlib import Path

import pytest

from spmkit.core.io import load_force, supported_force_extensions
from spmkit.core.models import ForceVolume

_JPK_SAMPLE = Path(__file__).resolve().parents[2] / "reference" / "jpk_samples" / "sample.jpk-force"


def test_supported_extensions_include_known_formats() -> None:
    exts = supported_force_extensions()
    assert ".nid" in exts
    assert ".jpk-force" in exts


def test_unknown_extension_raises() -> None:
    with pytest.raises(ValueError, match="no soportada"):
        load_force("curva.txt")


@pytest.mark.skipif(not _JPK_SAMPLE.exists(), reason="muestra JPK no disponible (gitignored)")
def test_jpk_single_curve_wraps_in_1x1_volume() -> None:
    volume = load_force(_JPK_SAMPLE)
    assert isinstance(volume, ForceVolume)
    assert volume.n_curves == 1
    assert volume.grid_shape == (1, 1)
    assert volume.curve(0).segments  # tiene al menos un segmento

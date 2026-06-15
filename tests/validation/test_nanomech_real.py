"""Regresión científica sobre un archivo de nanomecánica real del lab.

Fija el módulo de Young esperado y verifica que la orientación de los canales
de espectroscopía NO se voltea (las curvas conservan su posición espacial).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spmkit.core.analysis import mechanics
from spmkit.core.io import load_nid

_FILE = (
    Path(__file__).parents[2]
    / "reference"
    / "sample_files"
    / "Image00860 nanomech small nanofiber.nid"
)

pytestmark = pytest.mark.skipif(not _FILE.exists(), reason="archivo nanomech no presente")


@pytest.fixture(scope="module")
def force_channel():  # type: ignore[no-untyped-def]
    data = load_nid(_FILE)
    return next(c for c in data.channels if c.unit == "N")


def test_curves_extracted(force_channel):  # type: ignore[no-untyped-def]
    curves = mechanics.extract_curves(force_channel)
    assert len(curves) == 100
    assert len(curves[0]) == 1024


def test_young_modulus_regression(force_channel):  # type: ignore[no-untyped-def]
    curves = mechanics.extract_curves(force_channel)
    result = mechanics.fit_hertz(curves[len(curves) // 2], tip_radius=10e-9, model="sphere")
    # Valor de referencia validado (nanofibra polimérica blanda).
    assert result.young_modulus / 1e6 == pytest.approx(26.1, rel=0.05)
    assert 0 < result.contact_point < 5e-7
    assert result.adhesion > 0


def test_spec_channel_not_flipped(force_channel):  # type: ignore[no-untyped-def]
    # Los canales de espectroscopía tienen Dim1Name=SpecPoint y no se voltean.
    assert force_channel.metadata.get("Dim1Name", "").startswith("Spec")

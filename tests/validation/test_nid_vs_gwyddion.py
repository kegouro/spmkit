"""Validación científica: lectura .nid de spmkit vs export .gwy de Gwyddion.

Compara, para una misma medida, la lectura cruda del ``.nid`` contra el
``.gwy`` que el lab exportó desde Gwyddion (ground truth). Verifica que:

* La conversión a unidades físicas es exacta (canales no procesados → corr 1.0).
* La orientación coincide con Gwyddion (sin transformaciones extra).
* El canal de topografía procesado coincide tras nivelar (corr 1.0).

Se omite si no están los archivos pareados en ``reference/sample_files/``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

gwyfile = pytest.importorskip("gwyfile")

from spmkit.core.analysis import leveling  # noqa: E402
from spmkit.core.io import load_gwy, load_nid  # noqa: E402

_ROOT = Path(__file__).parents[2] / "reference" / "sample_files"
_PAIR = ("Image00851 small nanofiber.nid", "Image00851 small nanofiber.gwy")

pytestmark = pytest.mark.skipif(
    not (_ROOT / _PAIR[0]).exists() or not (_ROOT / _PAIR[1]).exists(),
    reason="archivos pareados .nid/.gwy no presentes",
)


@pytest.fixture(scope="module")
def pair():  # type: ignore[no-untyped-def]
    return load_nid(_ROOT / _PAIR[0]), load_gwy(_ROOT / _PAIR[1])


def _get(data, name, direction):  # type: ignore[no-untyped-def]
    return next(c for c in data.channels if c.name == name and c.direction == direction)


@pytest.mark.parametrize(
    "name,direction",
    [
        ("Phase", "forward"),
        ("Phase", "backward"),
        ("Z-Axis Sensor", "forward"),
        ("Z-Axis Sensor", "backward"),
        ("Z-Axis", "backward"),
    ],
)
def test_raw_channels_match_gwyddion_exactly(pair, name, direction):  # type: ignore[no-untyped-def]
    nid, gwy = pair
    a = _get(nid, name, direction).data
    g = _get(gwy, name, direction).data
    # Sin transformaciones: la orientación del parser ya coincide con Gwyddion.
    assert a.shape == g.shape
    corr = np.corrcoef(a.ravel(), g.ravel())[0, 1]
    assert corr == pytest.approx(1.0, abs=1e-9)
    # Relieve idéntico (la referencia Z absoluta puede diferir).
    assert np.max(np.abs((a - a.mean()) - (g - g.mean()))) / (np.ptp(a) or 1) < 1e-6


def test_units_consistent(pair):  # type: ignore[no-untyped-def]
    nid, gwy = pair
    assert _get(nid, "Z-Axis", "forward").unit == "m"
    assert _get(gwy, "Z-Axis", "forward").unit == "m"


def test_processed_topography_matches_after_leveling(pair):  # type: ignore[no-untyped-def]
    """El Z-Axis forward fue nivelado en Gwyddion; coincide tras nivelar ambos."""
    nid, gwy = pair
    a = leveling.align_rows(leveling.plane_fit(_get(nid, "Z-Axis", "forward")))
    g = leveling.align_rows(leveling.plane_fit(_get(gwy, "Z-Axis", "forward")))
    corr = np.corrcoef(a.data.ravel(), g.data.ravel())[0, 1]
    assert corr == pytest.approx(1.0, abs=1e-6)

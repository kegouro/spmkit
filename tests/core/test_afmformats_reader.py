"""Valida el lector afmformats contra samples open-source descargados.

Los samples se bajan con ``python scripts/fetch_samples.py`` a ``reference/samples/``
(gitignored). Sin ellos, o sin el extra ``afm``, los tests se saltan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("afmformats")

from spmkit.core.analysis.forcecurve import display_axis, fit_force_curve  # noqa: E402
from spmkit.core.io import inspect_any, load_any  # noqa: E402
from spmkit.core.models import ForceVolume  # noqa: E402
from spmkit.core.plugins import supported_extensions  # noqa: E402

_SAMPLES = Path(__file__).resolve().parents[2] / "reference" / "samples"


def _first(ext: str) -> Path | None:
    if not _SAMPLES.exists():
        return None
    return next(iter(_SAMPLES.glob(f"*{ext}")), None)


def test_afmformats_extensions_registered() -> None:
    exts = supported_extensions()
    for ext in (".ibw", ".jpk-qi-data", ".h5", ".jpk-force-map"):
        assert ext in exts


def test_load_asylum_ibw_and_fit() -> None:
    path = _first(".ibw")
    if path is None:
        pytest.skip("sin sample .ibw (corre scripts/fetch_samples.py)")
    info = inspect_any(path)
    assert info.kinds == ("force",)
    data, kind = load_any(path)
    assert kind == "force"
    assert isinstance(data, ForceVolume) and data.n_curves >= 1
    seg = data.curve(0).extend
    assert seg is not None and seg.force is not None
    fit = fit_force_curve(display_axis(seg.separation, seg.raw_height), seg.force, tip_radius=10e-9)
    assert fit.young_modulus > 0  # Asylum SiN: módulo positivo y sensato


def test_load_jpk_qi_map() -> None:
    path = _first(".jpk-qi-data")
    if path is None:
        pytest.skip("sin sample .jpk-qi-data")
    data, kind = load_any(path)
    assert kind == "force"
    assert isinstance(data, ForceVolume) and data.n_curves >= 1
    # cada curva trae approach (+ retract) calibrado
    assert data.curve(0).extend is not None
    assert data.curve(0).extend.force is not None

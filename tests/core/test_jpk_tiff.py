"""Lector de curvas de fuerza JPK-TIFF: conversión crudo→físico verificada."""

from __future__ import annotations

import numpy as np
import pytest

tifffile = pytest.importorskip("tifffile")  # requiere el extra 'jpk'

from spmkit.core.io.jpk_tiff import load_jpk_tiff, looks_like_jpk_tiff  # noqa: E402

_NAME = 32850  # tag del nombre de canal


def _slot_tags(specs):
    """Tags de slots: unidad en ``code``, LinearScaling en ``+1``, mult ``+2``, offset ``+3``."""
    tags = []
    for code, unit, mult, off in specs:
        tags += [
            (code, 2, len(unit) + 1, unit, False),
            (code + 1, 2, 14, "LinearScaling", False),
            (code + 2, 12, 1, float(mult), False),
            (code + 3, 12, 1, float(off), False),
        ]
    return tags


def _write_synthetic_jpk_tiff(path, raw_vd, raw_h, m_n, m_dm, m_h):
    """Escribe un JPK-TIFF mínimo: preview + (Height, vDeflection) × 2 segmentos."""

    def page(name, raw, slots):
        return raw, [(_NAME, 2, len(name) + 1, name, False)] + _slot_tags(slots)

    vd_slots = [(33026, "m", m_dm, 0.0), (33074, "N", m_n, 0.0)]
    h_slots = [(33026, "m", m_h, 0.0)]
    preview = (np.zeros((1, 4), np.uint8), [(32768, 2, 4, "jpk", False)])  # tag JPK para detección
    pages = [
        preview,
        page("Height (measured)", raw_h, h_slots),
        page("Vertical Deflection", raw_vd, vd_slots),
        page("Height (measured)", raw_h, h_slots),  # segmento 2 (retract)
        page("Vertical Deflection", raw_vd, vd_slots),
    ]
    with tifffile.TiffWriter(path) as tw:
        for raw, tags in pages:
            tw.write(raw, extratags=tags)


def test_jpk_tiff_conversion_exacta(tmp_path) -> None:
    """La conversión ``físico = crudo·mult`` recupera fuerza (N) y separación (m) exactas."""
    path = tmp_path / "curva_jpk"  # sin extensión, como el export real de JPK
    raw_vd = np.array([[100, 200, 300, 400]], dtype=np.int32)
    raw_h = np.array([[100, 200, 300, 400]], dtype=np.int32)
    m_n, m_dm, m_h = 1e-9, 1e-9, 1e-8  # N/cuenta, m/cuenta (defl), m/cuenta (altura)
    _write_synthetic_jpk_tiff(path, raw_vd, raw_h, m_n, m_dm, m_h)

    assert looks_like_jpk_tiff(path)  # detección por contenido (sin extensión)
    vol = load_jpk_tiff(path)
    assert vol.n_curves == 1
    curve = vol.curve(0)
    assert [s.segment_type for s in curve.segments] == ["extend", "retract"]

    ext = curve.extend
    np.testing.assert_allclose(ext.force, raw_vd[0] * m_n)  # fuerza N exacta
    # separación = altura − deflexión (ambas del crudo con su multiplicador)
    np.testing.assert_allclose(ext.separation, raw_h[0] * m_h - raw_vd[0] * m_dm)


def test_jpk_tiff_via_load_any(tmp_path) -> None:
    """``load_any`` reconoce el JPK-TIFF por contenido y devuelve un ForceVolume."""
    from spmkit.core.io.loadany import inspect_any, load_any

    path = tmp_path / "otra_curva"
    raw = np.array([[10, 20, 30]], dtype=np.int32)
    _write_synthetic_jpk_tiff(path, raw, raw, 1e-9, 1e-9, 1e-8)
    assert inspect_any(path).kinds == ("force",)
    data, kind = load_any(path)
    assert kind == "force" and data.n_curves == 1

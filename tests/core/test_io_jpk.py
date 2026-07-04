"""Tests del lector JPK ``.jpk-force`` (fixture sintético + sample real gated)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io.jpk import load_jpk_force

_REAL_SAMPLE = (
    Path(__file__).resolve().parents[2] / "reference" / "jpk_samples" / "sample.jpk-force"
)


def _segment_header(name: str) -> str:
    """Cabecera de segmento JPK mínima con las cadenas de conversión height/vDeflection."""
    return "\n".join(
        [
            f"force-segment-header.name.name={name}",
            "channel.height.data.type=short",
            "channel.height.data.encoder.scaling.multiplier=1.0E-9",
            "channel.height.data.encoder.scaling.offset=0.0",
            "channel.height.conversion-set.conversions.list=calibrated",
            "channel.height.conversion-set.conversion.calibrated.scaling.multiplier=1.0",
            "channel.height.conversion-set.conversion.calibrated.scaling.offset=0.0",
            "channel.vDeflection.data.type=short",
            "channel.vDeflection.data.encoder.scaling.multiplier=1.0",
            "channel.vDeflection.data.encoder.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversions.list=distance force",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.multiplier=2.0E-8",
            "channel.vDeflection.conversion-set.conversion.distance.scaling.offset=0.0",
            "channel.vDeflection.conversion-set.conversion.force.scaling.multiplier=0.5",
            "channel.vDeflection.conversion-set.conversion.force.scaling.offset=0.0",
        ]
    )


def _make_synthetic_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """Escribe un .jpk-force mínimo con dos segmentos (extend + retract)."""
    h_bytes = raw_h.astype(">i2").tobytes()
    vd_bytes = raw_vd.astype(">i2").tobytes()
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("header.properties", "jpk-data-file=spm-forcefile\n")
        for seg, name in ((0, "extend-spm"), (1, "retract-spm")):
            zf.writestr(f"segments/{seg}/segment-header.properties", _segment_header(name))
            zf.writestr(f"segments/{seg}/channels/height.dat", h_bytes)
            zf.writestr(f"segments/{seg}/channels/vDeflection.dat", vd_bytes)


def test_load_synthetic_jpk_force(tmp_path: Path) -> None:
    raw_h = np.arange(8, dtype=np.int16) * 10
    raw_vd = np.arange(8, dtype=np.int16)
    jpk = tmp_path / "curve.jpk-force"
    _make_synthetic_jpk(jpk, raw_h, raw_vd)

    curve = load_jpk_force(jpk)

    assert len(curve.segments) == 2
    ext, ret = curve.extend, curve.retract
    assert ext is not None and ret is not None
    assert ext.segment_type == "extend" and ext.direction == "approach"
    assert ret.segment_type == "retract"
    assert ext.state == "force_n"

    # Cadena de conversión recuperada exactamente.
    assert np.allclose(ext.raw_height, raw_h * 1.0e-9)
    assert np.allclose(ext.deflection, raw_vd * 2.0e-8)
    assert np.allclose(ext.force, raw_vd * 2.0e-8 * 0.5)
    assert np.allclose(ext.separation, raw_h * 1.0e-9 - raw_vd * 2.0e-8)

    # Calibración leída de los metadatos (InVOLS = slot distance, k = slot force).
    assert curve.calibration is not None
    assert curve.calibration.invols == pytest.approx(2.0e-8)
    assert curve.calibration.spring_constant == pytest.approx(0.5)
    assert curve.calibration.method == "jpk_metadata"


def test_load_jpk_without_segments_raises(tmp_path: Path) -> None:
    jpk = tmp_path / "bad.jpk-force"
    with zipfile.ZipFile(jpk, "w") as zf:
        zf.writestr("header.properties", "jpk-data-file=spm-forcefile\n")
    with pytest.raises(ValueError, match="sin segmentos"):
        load_jpk_force(jpk)


@pytest.mark.skipif(not _REAL_SAMPLE.exists(), reason="sample JPK real no disponible (gitignored)")
def test_load_real_jpk_force() -> None:
    """Valida contra la curva JPK real (afmformats) del spike, si está disponible."""
    curve = load_jpk_force(_REAL_SAMPLE)
    assert len(curve.segments) >= 2
    assert curve.calibration is not None
    assert curve.calibration.invols == pytest.approx(7.0e-8, rel=0.3)
    assert curve.calibration.spring_constant == pytest.approx(0.0435, rel=0.3)
    ext = curve.extend
    assert ext is not None and ext.force is not None
    assert np.all(np.isfinite(ext.force))
    assert len(ext) == 2000  # num-points del sample

"""Core contract tests for gwydion_mark_scars (production Mark Scars)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_mark_scars
from spmkit.core.models.spmdata import SPMChannel


def _channel(data: np.ndarray, name: str = "markscars") -> SPMChannel:
    return SPMChannel(
        name=name, data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]))


def _field(rows: int, cols: int, band_row: int | None = None,
           value: float = 5.0) -> np.ndarray:
    field = np.zeros((rows, cols), dtype=np.float64)
    if band_row is not None:
        field[band_row, :] = value
    return field


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


# ---------------------------------------------------------------------------
# Public parameter validation
# ---------------------------------------------------------------------------


def test_threshold_domain_validation() -> None:
    ch = _channel(_field(10, 10, 4))
    for kwargs in [{"threshold_high": -0.1}, {"threshold_high": 2.1},
                   {"threshold_low": -0.1}, {"threshold_low": 2.1},
                   {"threshold_high": np.nan}, {"threshold_low": np.inf}]:
        with pytest.raises(ValueError):
            gwydion_mark_scars(ch, **kwargs)


def test_integer_domain_validation() -> None:
    ch = _channel(_field(10, 10, 4))
    for kwargs in [{"min_length": 0}, {"min_length": 1025},
                   {"max_width": 0}, {"max_width": 17}]:
        with pytest.raises(ValueError):
            gwydion_mark_scars(ch, **kwargs)
    with pytest.raises(TypeError):
        gwydion_mark_scars(ch, min_length=4.5)
    with pytest.raises(TypeError):
        gwydion_mark_scars(ch, max_width=True)


def test_polarity_and_combine_validation() -> None:
    ch = _channel(_field(10, 10, 4))
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, polarity="sideways")
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, combine="xor")
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, combine="union")
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, combine="intersection")


def test_channel_and_mask_validation() -> None:
    ch = _channel(_field(10, 10, 4))
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, existing_mask=np.zeros((9, 9)))
    with pytest.raises(ValueError):
        gwydion_mark_scars(ch, existing_mask=np.full((10, 10), np.nan))
    bad = SPMChannel(name="x", data=np.full((4, 4), np.nan), unit="nm",
                     x_range=4.0, y_range=4.0)
    with pytest.raises(ValueError):
        gwydion_mark_scars(bad)
    flat = SPMChannel(name="x", data=np.zeros(16), unit="nm",
                      x_range=4.0, y_range=4.0)
    with pytest.raises(ValueError):
        gwydion_mark_scars(flat)


# ---------------------------------------------------------------------------
# Detector semantics
# ---------------------------------------------------------------------------


def test_threshold_sanitization() -> None:
    # reversed thresholds: effective high becomes low (0.666)
    field = _field(10, 10, 4)
    mask_san = gwydion_mark_scars(
        _channel(field), threshold_high=0.25, threshold_low=0.666,
        min_length=4, max_width=1, polarity="positive")
    mask_ref = gwydion_mark_scars(
        _channel(field), threshold_high=0.666, threshold_low=0.666,
        min_length=4, max_width=1, polarity="positive")
    assert np.array_equal(_bits(mask_san), _bits(mask_ref))


def test_positive_negative_both() -> None:
    field = np.zeros((12, 10), dtype=np.float64)
    field[3, :] = 5.0
    field[8, :] = -5.0
    pos = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                             polarity="positive")
    neg = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                             polarity="negative")
    both = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                              polarity="both")
    assert np.all(pos[3, :] == 1.0) and not np.any(pos[8, :])
    assert np.all(neg[8, :] == 1.0) and not np.any(neg[3, :])
    # Both = two detector runs plus fmax union (binary union here)
    assert np.array_equal(_bits(both), _bits(np.fmax(pos, neg)))
    assert int(np.count_nonzero(both)) == 20


def test_hard_seed_and_soft_attachment() -> None:
    field = np.zeros((10, 8), dtype=np.float64)
    field[4, 0:5] = 5.0   # hard
    field[4, 5:8] = 1.0   # soft shoulder
    mask = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                              polarity="positive")
    assert int(np.count_nonzero(mask)) == 8   # entire row attached


def test_soft_only_rejected() -> None:
    # A uniform single-row band always has weight sqrt(5) ~ 2.236, so a
    # soft-only configuration (weight in [threshold_low, threshold_high))
    # needs threshold_high > sqrt(5), which is outside the public domain
    # [0, 2].  Mirroring the frozen campaign (C05/C07), the kernel-level
    # contract is exercised directly with threshold_high=3.0.
    from spmkit.core.analysis._gwydion_mark_scars import (
        _gwydion_mark_scars_result,
    )
    field = np.zeros((10, 8), dtype=np.float64)
    field[4, :] = 1.0
    result = _gwydion_mark_scars_result(
        field, threshold_high=3.0, threshold_low=0.25, min_length=4,
        max_width=1, polarity="positive")
    assert int(np.count_nonzero(result.final_mask)) == 0
    assert result.guard_reason is None


def test_width_boundaries() -> None:
    field = np.zeros((10, 8), dtype=np.float64)
    field[4, :] = 5.0
    field[5, :] = 5.0
    # width exactly max_width -> marked
    mask = gwydion_mark_scars(_channel(field), min_length=4, max_width=2,
                              polarity="positive")
    assert int(np.count_nonzero(mask)) == 16
    field2 = np.zeros((10, 8), dtype=np.float64)
    field2[4, :] = 5.0
    field2[5, :] = 5.0
    field2[6, :] = 5.0
    # width max_width + 1 -> window cannot close -> rejected
    mask2 = gwydion_mark_scars(_channel(field2), min_length=4, max_width=2,
                               polarity="positive")
    assert int(np.count_nonzero(mask2)) == 0


def test_length_boundaries() -> None:
    field = np.zeros((10, 8), dtype=np.float64)
    field[4, 0:4] = 5.0
    assert int(np.count_nonzero(
        gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                           polarity="positive"))) == 4
    field2 = np.zeros((10, 8), dtype=np.float64)
    field2[4, 0:3] = 5.0
    assert int(np.count_nonzero(
        gwydion_mark_scars(_channel(field2), min_length=4, max_width=1,
                           polarity="positive"))) == 0


def test_first_last_row_excluded() -> None:
    field = np.zeros((10, 8), dtype=np.float64)
    field[0, :] = 5.0
    field[9, :] = -5.0
    mask = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                              polarity="both")
    assert int(np.count_nonzero(mask)) == 0


def test_horizontal_edge_runs() -> None:
    field = np.zeros((10, 8), dtype=np.float64)
    field[6, :] = 3.0
    mask = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                              polarity="positive")
    assert int(np.count_nonzero(mask)) == 8


def test_constant_field_guard() -> None:
    mask = gwydion_mark_scars(_channel(np.ones((10, 10))), min_length=2,
                              max_width=1, polarity="both")
    assert int(np.count_nonzero(mask)) == 0


def test_minimum_dimensions() -> None:
    field = np.zeros((3, 2), dtype=np.float64)
    field[1, :] = 5.0
    mask = gwydion_mark_scars(_channel(field), min_length=1, max_width=1,
                              polarity="positive")
    assert int(np.count_nonzero(mask)) == 2


def test_binary_and_contiguous_output() -> None:
    field = _field(10, 10, 4)
    mask = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                              polarity="positive")
    assert mask.dtype == np.float64
    assert mask.flags.c_contiguous
    assert set(np.unique(mask)) <= {0.0, 1.0}
    # output is independent of the returned array
    mask[0, 0] = 99.0
    mask2 = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                               polarity="positive")
    assert mask2[0, 0] == 0.0


# ---------------------------------------------------------------------------
# Combine semantics
# ---------------------------------------------------------------------------


def test_replace_union_intersection() -> None:
    field = _field(10, 10, 4)
    existing = np.zeros((10, 10), dtype=np.float64)
    existing[2, :] = 1.0
    replaced = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                                  polarity="positive", existing_mask=existing,
                                  combine="replace")
    plain = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                               polarity="positive")
    assert np.array_equal(_bits(replaced), _bits(plain))
    assert int(np.count_nonzero(plain)) == 10   # full 10-column row
    union = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                               polarity="positive", existing_mask=existing,
                               combine="union")
    assert int(np.count_nonzero(union)) == 20
    assert np.array_equal(_bits(union), _bits(np.fmax(plain, existing)))
    existing2 = np.zeros((10, 10), dtype=np.float64)
    existing2[4, 0:4] = 1.0
    intersection = gwydion_mark_scars(
        _channel(field), min_length=4, max_width=1, polarity="positive",
        existing_mask=existing2, combine="intersection")
    assert int(np.count_nonzero(intersection)) == 4
    assert np.array_equal(_bits(intersection), _bits(np.fmin(plain, existing2)))


def test_non_binary_existing_mask_preserved_through_fmax() -> None:
    field = _field(10, 10, 4)
    existing = np.zeros((10, 10), dtype=np.float64)
    existing[2, 0:4] = 0.5   # finite non-binary values
    union = gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                               polarity="positive", existing_mask=existing,
                               combine="union")
    assert 0.5 in np.unique(union)
    assert not (set(np.unique(union)) <= {0.0, 1.0})


def test_input_and_existing_mask_non_mutation() -> None:
    field = _field(10, 10, 4)
    existing = np.zeros((10, 10), dtype=np.float64)
    existing[2, :] = 1.0
    field_bits = _bits(field).copy()
    existing_bits = _bits(existing).copy()
    gwydion_mark_scars(_channel(field), min_length=4, max_width=1,
                       polarity="both", existing_mask=existing,
                       combine="union")
    assert np.array_equal(_bits(field), field_bits)
    assert np.array_equal(_bits(existing), existing_bits)


def test_no_detection_returns_all_zero() -> None:
    mask = gwydion_mark_scars(_channel(np.zeros((10, 10))), min_length=4,
                              max_width=1, polarity="both")
    assert int(np.count_nonzero(mask)) == 0
    assert set(np.unique(mask)) <= {0.0}

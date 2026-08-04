"""Core contract tests for Gwydion 2.71 Mark Inverted Rows.

Tests the public and private contracts independently of the frozen fixture
comparison, using source-derived analytic expectations.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_mark_inverted_rows
from spmkit.core.analysis._gwydion_mark_inverted_rows import (
    _gwydion_mark_inverted_rows_result,
)
from spmkit.core.models.spmdata import SPMChannel

BASE = np.array([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float64)


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="test",
        data=np.asarray(data, dtype=np.float64),
        unit="nm",
        x_range=float(data.shape[1]),
        y_range=float(data.shape[0]),
    )


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _marked_rows(mask: np.ndarray) -> list[int]:
    return [int(r) for r in range(mask.shape[0]) if np.any(mask[r] == 1.0)]


def test_input_non_mutation_and_mask_independence() -> None:
    data = np.vstack([BASE + i for i in range(5)])
    channel = _channel(data)
    original = data.copy()
    mask = gwydion_mark_inverted_rows(channel)
    assert np.array_equal(_bits(channel.data), _bits(original))
    assert mask.shape == data.shape
    assert mask.dtype == np.float64
    assert mask.flags.c_contiguous
    assert mask is not channel.data
    # returned array is an independent copy
    mask[0, 0] = 12345.0
    assert np.all(channel.data != 12345.0)


def test_mask_values_exactly_binary() -> None:
    data = np.vstack([BASE, -BASE, BASE, BASE, BASE])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert set(np.unique(mask)) <= {0.0, 1.0}


def test_all_positive_correlations_zero_mask() -> None:
    data = np.vstack([BASE + i for i in range(5)])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert np.all(mask == 0.0)


def test_one_inverted_interior_row() -> None:
    data = np.vstack([BASE, -BASE, BASE, BASE, BASE])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert _marked_rows(mask) == [1]


def test_first_and_last_row_inversion() -> None:
    data = np.vstack([-BASE, BASE, BASE, BASE, BASE])
    assert _marked_rows(gwydion_mark_inverted_rows(_channel(data))) == [0]
    data = np.vstack([BASE, BASE, BASE, BASE, -BASE])
    assert _marked_rows(gwydion_mark_inverted_rows(_channel(data))) == [4]


def test_consecutive_inverted_rows() -> None:
    scaled = -0.8 * BASE
    data = np.vstack([BASE, BASE, scaled, scaled, BASE])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert _marked_rows(mask) == [2, 3]


def test_repeated_toggles() -> None:
    data = np.vstack([BASE, -0.8 * BASE, 0.7 * BASE, -0.6 * BASE, 0.5 * BASE])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert _marked_rows(mask) == [0, 1, 3]


def test_constant_field_guard() -> None:
    data = np.full((5, 5), 5.0, dtype=np.float64)
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert np.all(mask == 0.0)


def test_constant_row_in_varying_field() -> None:
    data = np.vstack([BASE, np.full(5, 3.0), BASE, BASE, BASE])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert np.all(mask == 0.0)  # zero weights -> no negative -> no mask


def test_strict_first_anchor_tie() -> None:
    data = np.vstack([BASE, BASE, -BASE, -BASE, BASE])
    result = _gwydion_mark_inverted_rows_result(data)
    # weights [+2.5, -2.5, +2.5, -2.5]: w0 and w2 tie -> first maximum
    assert result.anchor_index == 0
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert _marked_rows(mask) == [2, 3]


@pytest.mark.parametrize("shape", [(2, 5), (3, 2)])
def test_dimension_guards(shape) -> None:
    data = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)
    result = _gwydion_mark_inverted_rows_result(data)
    assert result.guard_triggered
    assert result.generated_mask is None
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert np.all(mask == 0.0)


def test_private_existing_mask_preserved_on_no_negative() -> None:
    data = np.vstack([BASE + i for i in range(5)])
    existing = np.zeros((5, 5), dtype=np.float64)
    existing[2, :] = 1.0
    before = existing.copy()
    result = _gwydion_mark_inverted_rows_result(data, existing_mask=existing)
    assert result.generated_mask is None
    assert result.would_create_mask is False
    assert result.would_overwrite_existing_mask is False
    assert np.array_equal(_bits(existing), _bits(before))


def test_private_existing_mask_overwritten_on_detection() -> None:
    data = np.vstack([BASE, -BASE, BASE, BASE, BASE])
    existing = np.zeros((5, 5), dtype=np.float64)
    existing[0, :] = 1.0
    existing[1, :] = 0.5
    existing[4, :] = 1.0
    result = _gwydion_mark_inverted_rows_result(data, existing_mask=existing)
    assert result.generated_mask is not None
    assert result.would_create_mask is True
    assert result.would_overwrite_existing_mask is True
    assert np.array_equal(_bits(existing), _bits(result.generated_mask))
    assert _marked_rows(existing) == [1]


def test_public_all_zero_adaptation_on_no_detection() -> None:
    data = np.vstack([BASE + i for i in range(5)])
    mask = gwydion_mark_inverted_rows(_channel(data))
    assert mask.shape == data.shape
    assert np.all(mask == 0.0)


def test_input_never_modified_privately() -> None:
    data = np.vstack([BASE, -BASE, BASE, BASE, BASE])
    original = data.copy()
    _gwydion_mark_inverted_rows_result(data)
    assert np.array_equal(_bits(data), _bits(original))


def test_non_finite_rejection() -> None:
    bad = np.array([[1.0, np.nan], [2.0, 3.0]])
    with pytest.raises(ValueError, match="finite"):
        gwydion_mark_inverted_rows(_channel(bad))
    bad = np.array([[1.0, np.inf], [2.0, 3.0]])
    with pytest.raises(ValueError, match="finite"):
        gwydion_mark_inverted_rows(_channel(bad))

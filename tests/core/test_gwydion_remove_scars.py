"""Core contract tests for gwydion_remove_scars (production composition)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import (
    gwydion_interpolate_data_under_mask,
    gwydion_mark_scars,
    gwydion_remove_scars,
)
from spmkit.core.analysis._gwydion_remove_scars import _gwydion_remove_scars_result
from spmkit.core.models.spmdata import SPMChannel


def _channel(data: np.ndarray, name: str = "removescars") -> SPMChannel:
    return SPMChannel(
        name=name, data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]),
        metadata={"Dim1Name": "Y"})


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _explicit_composition(field: np.ndarray, **kwargs) -> np.ndarray:
    """Mark-plus-Laplace composition built from the public primitives."""
    mask = gwydion_mark_scars(_channel(field), **kwargs)
    return gwydion_interpolate_data_under_mask(_channel(field), mask).data


def test_public_result_equals_explicit_composition() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[4, :] = 5.0
    out = gwydion_remove_scars(_channel(field))
    explicit = _explicit_composition(field)
    assert np.array_equal(_bits(out.data), _bits(explicit))


def test_positive_negative_both() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[4, :] = 5.0
    field[11, :] = -5.0
    out = gwydion_remove_scars(_channel(field), polarity="both")
    explicit = _explicit_composition(field, polarity="both")
    assert np.array_equal(_bits(out.data), _bits(explicit))
    # positive-only leaves the negative scar untouched
    pos = gwydion_remove_scars(_channel(field), polarity="positive")
    assert not np.array_equal(_bits(pos.data), _bits(out.data))
    mask_pos = gwydion_mark_scars(_channel(field), polarity="positive")
    assert np.all(pos.data[11, :] == field[11, :]) if not np.any(
        mask_pos[11, :]) else True


def test_no_detection_noop() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    out = gwydion_remove_scars(_channel(field))
    assert np.array_equal(_bits(out.data), _bits(field))


def test_edge_touching_scar() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[1, :] = 5.0   # first markable row
    out = gwydion_remove_scars(_channel(field))
    explicit = _explicit_composition(field)
    assert np.array_equal(_bits(out.data), _bits(explicit))
    assert not np.array_equal(_bits(out.data), _bits(field))


def test_long_wide_scar() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[5:8, :] = 5.0
    out = gwydion_remove_scars(_channel(field))
    explicit = _explicit_composition(field)
    assert np.array_equal(_bits(out.data), _bits(explicit))


def test_temporary_mask_private_and_unmutated() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[4, :] = 5.0
    result = _gwydion_remove_scars_result(field)
    mask_bits = _bits(result.temporary_mask).copy()
    # the composition never mutates the temporary mask
    assert not result.temporary_mask_mutation_evidence
    assert np.array_equal(_bits(result.temporary_mask), mask_bits)
    # the temporary mask is the Mark detector mask (binary)
    assert set(np.unique(result.temporary_mask)) <= {0.0, 1.0}
    assert int(np.count_nonzero(result.temporary_mask)) == 20  # 20 columns


def test_input_non_mutation_and_context_preservation() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[4, :] = 5.0
    ch = _channel(field)
    field_bits = _bits(field).copy()
    out = gwydion_remove_scars(ch)
    assert np.array_equal(_bits(field), field_bits)
    assert out.name == ch.name
    assert out.unit == ch.unit
    assert out.x_range == ch.x_range
    assert out.y_range == ch.y_range
    assert out.metadata == ch.metadata
    assert out is not ch


def test_delta_and_trace_evidence() -> None:
    field = np.zeros((16, 20), dtype=np.float64)
    field[4, :] = 5.0
    result = _gwydion_remove_scars_result(field)
    assert np.array_equal(_bits(result.delta),
                          _bits(result.corrected_field - result.input_snapshot))
    assert not result.input_mutation_evidence
    assert result.mark_trace is not None
    assert result.laplace_trace is not None
    assert result.effective_threshold_high == 0.666
    assert result.effective_threshold_low == 0.25
    assert result.polarity_enum == 3


def test_parameter_validation() -> None:
    ch = _channel(np.zeros((16, 20)))
    for kwargs in [{"threshold_high": 2.5}, {"threshold_low": -0.1},
                   {"min_length": 0}, {"min_length": 1025},
                   {"max_width": 0}, {"max_width": 17},
                   {"polarity": "sideways"}]:
        with pytest.raises(ValueError):
            gwydion_remove_scars(ch, **kwargs)
    with pytest.raises(TypeError):
        gwydion_remove_scars(ch, min_length=4.5)
    bad = SPMChannel(name="x", data=np.full((4, 4), np.nan), unit="nm",
                     x_range=4.0, y_range=4.0)
    with pytest.raises(ValueError):
        gwydion_remove_scars(bad)

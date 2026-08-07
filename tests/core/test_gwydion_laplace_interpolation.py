"""Core contract tests for gwydion_interpolate_data_under_mask (Laplace)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_interpolate_data_under_mask
from spmkit.core.analysis._gwydion_laplace import _gwydion_laplace_result
from spmkit.core.models.spmdata import SPMChannel


def _channel(data: np.ndarray, name: str = "laplace") -> SPMChannel:
    return SPMChannel(
        name=name, data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]),
        metadata={"Dim1Name": "Y", "custom": 7})


def _mask(shape: tuple[int, int], *rects: tuple[int, int, int, int],
          value: float = 1.0) -> np.ndarray:
    m = np.zeros(shape, dtype=np.float64)
    for r0, r1, c0, c1 in rects:
        m[r0:r1 + 1, c0:c1 + 1] = value
    return m


def _gradient(shape: tuple[int, int]) -> np.ndarray:
    yres, xres = shape
    return np.asarray(
        [[float(i + j) for j in range(xres)] for i in range(yres)],
        dtype=np.float64)


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _assert_unchanged(out: SPMChannel, inp: np.ndarray) -> None:
    assert np.array_equal(_bits(out.data), _bits(inp))


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def test_empty_mask_unchanged() -> None:
    field = _gradient((6, 8))
    out = gwydion_interpolate_data_under_mask(_channel(field), np.zeros((6, 8)))
    _assert_unchanged(out, field)
    assert out.data is not field  # independent copy


def test_whole_field_mask_zeros() -> None:
    field = _gradient((6, 6))
    out = gwydion_interpolate_data_under_mask(
        _channel(field), np.ones((6, 6)))
    assert not np.any(out.data != 0.0)


def test_isolated_pixels() -> None:
    field = _gradient((5, 5))
    interior = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((5, 5), (2, 2, 2, 2)))
    assert interior.data[2, 2] == (field[1, 2] + field[3, 2]
                                   + field[2, 1] + field[2, 3]) / 4.0
    edge = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((5, 5), (0, 0, 2, 2)))
    assert edge.data[0, 2] == (field[1, 2] + field[0, 1] + field[0, 3]) / 3.0
    corner = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((5, 5), (0, 0, 0, 0)))
    assert corner.data[0, 0] == (field[1, 0] + field[0, 1]) / 2.0


def test_thin_corridors() -> None:
    field = _gradient((5, 7))          # 5 rows, 7 columns (fixture L05)
    horiz = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((5, 7), (2, 2, 1, 5)))
    # exact linear continuation: d = i + j (fully interior corridor); the
    # Thomas elimination rounds the middle pixel one ULP below the exact
    # value (frozen L05/L06 characterization, bitwise vs the compiled probe)
    assert list(horiz.data[2, 1:6]) == [3.0, 4.0, 4.999999999999999,
                                        6.0, 7.0]
    field_v = _gradient((7, 5))        # 7 rows, 5 columns (fixture L06)
    vert = gwydion_interpolate_data_under_mask(
        _channel(field_v), _mask((7, 5), (1, 5, 3, 3)))
    assert list(vert.data[1:6, 3]) == [4.0, 5.0, 5.999999999999999,
                                       7.0, 8.0]


def test_three_pixel_l() -> None:
    field = _gradient((6, 6))
    m = _mask((6, 6), (2, 2, 2, 3), (3, 3, 2, 2))
    out = gwydion_interpolate_data_under_mask(_channel(field), m)
    assert out.data[2, 2] == 4.0
    assert out.data[2, 3] == 5.0
    assert out.data[3, 2] == 5.0


def test_interior_component() -> None:
    field = _gradient((10, 12))
    out = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((10, 12), (4, 6, 3, 7)))
    # linear continuation is harmonic: d = i + j exactly
    for i in range(4, 7):
        for j in range(3, 8):
            assert out.data[i, j] == float(i + j)


def test_disconnected_components() -> None:
    field = _gradient((12, 12))
    m = _mask((12, 12), (2, 3, 2, 4), (7, 9, 8, 10))
    out = gwydion_interpolate_data_under_mask(_channel(field), m)
    assert out.data[2, 3] == 5.0 and out.data[7, 9] == 16.0


def test_edge_and_corner_components() -> None:
    field = _gradient((10, 10))
    edge = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((10, 10), (0, 2, 3, 5)))
    assert edge.data[0, 3] != 0.0 and not np.isnan(edge.data[0, 3])
    corner = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((10, 10), (0, 1, 0, 2)))
    assert corner.data[0, 0] != 0.0 and not np.isnan(corner.data[0, 0])


def test_entire_masked_row() -> None:
    field = _gradient((10, 10))
    out = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((10, 10), (4, 4, 0, 9)))
    row = out.data[4, :]
    assert np.all(np.isfinite(row))
    # the row touches both image edges, so the edge pixels carry the
    # Neumann-by-omission condition and the solution is not the linear ramp;
    # verify the discrete equations directly
    for j in range(10):
        if 0 < j < 9:
            lhs = 4 * row[j] - row[j - 1] - row[j + 1]
            rhs = field[3, j] + field[5, j]
        else:
            lhs = 3 * row[j] - (row[j - 1] if j else row[j + 1])
            rhs = field[3, j] + field[5, j]
        assert abs(lhs - rhs) < 1e-9
    # unmasked rows unchanged
    for i in (0, 1, 2, 3, 5, 6, 7, 8, 9):
        assert list(out.data[i, :]) == list(field[i, :])


def test_constant_boundary() -> None:
    field = np.full((8, 8), 3.0)
    out = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((8, 8), (3, 4, 3, 4)))
    assert not np.any(out.data != 3.0)


def test_strict_mask_predicate() -> None:
    field = _gradient((8, 8))
    m = _mask((8, 8), (2, 3, 2, 4), value=0.5)
    m[5, 5] = -1.0
    m[6, 2] = 0.0
    m[1, 5] = 1.0
    result = _gwydion_laplace_result(field, m)
    solved = set(result.solved_coordinates)
    assert (2, 2) in solved and (2, 3) in solved   # 0.5 counts as masked
    assert (1, 5) in solved                         # 1.0 counts as masked
    assert (5, 5) not in solved                     # -1.0 fixed
    assert (6, 2) not in solved                     # 0.0 fixed
    out = gwydion_interpolate_data_under_mask(_channel(field), m)
    assert out.data[5, 5] == field[5, 5]
    assert out.data[6, 2] == field[6, 2]


def test_calibration_independence() -> None:
    field = _gradient((8, 8))
    m = _mask((8, 8), (3, 5, 2, 4))
    a = gwydion_interpolate_data_under_mask(_channel(field), m)
    b = gwydion_interpolate_data_under_mask(
        SPMChannel(name="x", data=field.copy(), unit="m", x_range=0.123,
                   y_range=4.56), m)
    assert np.array_equal(_bits(a.data), _bits(b.data))


def test_signed_zero_behavior() -> None:
    field = np.full((5, 5), -0.0)
    out = gwydion_interpolate_data_under_mask(
        _channel(field), _mask((5, 5), (2, 2, 2, 2)))
    # all-negative-zero ring: the mean preserves -0.0 (dynamically linked
    # build semantics; the frozen source fold seeded with 0.0 gives +0.0)
    assert int(out.data[2, 2].view(np.uint64)) == 0x8000000000000000


def test_degenerate_dimensions() -> None:
    one_masked = gwydion_interpolate_data_under_mask(
        _channel(np.array([[7.0]])), np.array([[1.0]]))
    assert one_masked.data[0, 0] == 0.0
    one_unmasked = gwydion_interpolate_data_under_mask(
        _channel(np.array([[7.0]])), np.array([[0.0]]))
    assert one_unmasked.data[0, 0] == 7.0
    row = gwydion_interpolate_data_under_mask(
        _channel(np.array([[1.0, 3.0, 5.0]])),
        np.array([[0.0, 1.0, 0.0]]))
    assert row.data[0, 1] == 3.0
    col = gwydion_interpolate_data_under_mask(
        _channel(np.array([[2.0], [6.0], [10.0]])),
        np.array([[0.0], [1.0], [0.0]]))
    assert col.data[1, 0] == 6.0


# ---------------------------------------------------------------------------
# Non-mutation, context and validation
# ---------------------------------------------------------------------------


def test_input_and_mask_non_mutation() -> None:
    field = _gradient((8, 8))
    m = _mask((8, 8), (3, 5, 2, 4))
    field_bits = _bits(field).copy()
    mask_bits = _bits(m).copy()
    gwydion_interpolate_data_under_mask(_channel(field), m)
    assert np.array_equal(_bits(field), field_bits)
    assert np.array_equal(_bits(m), mask_bits)


def test_unmasked_pixels_bitwise_unchanged() -> None:
    field = _gradient((8, 8))
    m = _mask((8, 8), (3, 5, 2, 4))
    m[6, 6] = 0.5
    out = gwydion_interpolate_data_under_mask(_channel(field), m)
    for i in range(8):
        for j in range(8):
            if m[i, j] <= 0.0:
                assert out.data[i, j] == field[i, j]


def test_channel_context_preserved() -> None:
    field = _gradient((6, 8))
    ch = _channel(field)
    out = gwydion_interpolate_data_under_mask(ch, _mask((6, 8), (2, 3, 2, 4)))
    assert out.name == ch.name
    assert out.unit == ch.unit
    assert out.x_range == ch.x_range
    assert out.y_range == ch.y_range
    assert out.direction == ch.direction
    assert out.group == ch.group
    assert out.metadata == ch.metadata
    assert out is not ch


def test_convergence_diagnostics() -> None:
    field = _gradient((10, 12))
    result = _gwydion_laplace_result(field, _mask((10, 12), (4, 6, 3, 7)))
    assert result.max_residual <= 1e-12
    assert result.component_count >= 1
    assert len(result.iteration_counts) == result.component_count
    assert result.unmasked_mutation_count == 0
    assert not result.mask_mutation_evidence
    assert not result.input_mutation_evidence


def test_validation_errors() -> None:
    field = _gradient((8, 8))
    with pytest.raises(ValueError):
        gwydion_interpolate_data_under_mask(_channel(field), np.zeros((9, 8)))
    with pytest.raises(ValueError):
        gwydion_interpolate_data_under_mask(_channel(field), np.zeros((8, 8, 1)))
    with pytest.raises(ValueError):
        gwydion_interpolate_data_under_mask(
            _channel(field), np.full((8, 8), np.nan))
    with pytest.raises(ValueError):
        gwydion_interpolate_data_under_mask(
            SPMChannel(name="x", data=np.full((4, 4), np.inf), unit="nm",
                       x_range=4.0, y_range=4.0), np.zeros((4, 4)))
    with pytest.raises(TypeError):
        gwydion_interpolate_data_under_mask(
            SPMChannel(name="x", data=np.zeros((4, 4)), unit="nm",
                       x_range=4.0, y_range=4.0),
            np.zeros((4, 4), dtype=complex))

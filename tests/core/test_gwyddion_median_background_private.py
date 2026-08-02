"""Focused tests for the private Gwyddion 2.71 Median Background kernel."""

from __future__ import annotations

import json
from functools import cache, lru_cache
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis._median_background import (
    _gwyddion_median_background_result,
    _median_background_active_offsets,
    _median_background_kernel_spec,
)

_FIXTURE_DIR = (
    Path(__file__).parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "median_background"
)
_FIXTURE_PATH = _FIXTURE_DIR / "median_background_reference.npz"
_MANIFEST_PATH = _FIXTURE_DIR / "median_background_reference.json"
_KERNEL_INVENTORY = {
    1: (3, 9, 4, "direct"),
    2: (5, 21, 10, "direct"),
    3: (7, 37, 18, "radixtree"),
    4: (9, 69, 34, "radixtree"),
    20: (41, 1313, 656, "radixtree"),
    1024: (2049, 3297401, 1648700, "radixtree"),
}
_UINT64_MASK = (1 << 64) - 1
_UINT64_SIGN = 1 << 63


@lru_cache(maxsize=1)
def _fixture() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    """Load the frozen fixture only as test evidence."""
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    arrays: dict[str, np.ndarray] = {}
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        for name in archive.files:
            arrays[name] = np.array(archive[name], dtype=np.float64, order="C", copy=True)
    return manifest, arrays


def _case(case_name: str) -> dict[str, object]:
    manifest, _ = _fixture()
    for case in manifest["cases"]:  # type: ignore[index]
        if case["name"] == case_name:
            return case
    raise AssertionError(f"frozen fixture case was not found: {case_name}")


@cache
def _result_for_case(case_name: str) -> tuple[np.ndarray, np.ndarray, object]:
    case = _case(case_name)
    _, arrays = _fixture()
    keys = case["arrays"]
    return _gwyddion_median_background_result(
        arrays[keys["input"]],  # type: ignore[index]
        case["radius"],
    )


def _ordered_uint64(bits: int) -> int:
    """Map IEEE-754 bits to an ordering suitable for a ULP distance."""
    if bits & _UINT64_SIGN:
        return (-bits) & _UINT64_MASK
    return bits | _UINT64_SIGN


def _assert_bitwise_equal(
    case_name: str,
    array_name: str,
    expected: np.ndarray,
    actual: np.ndarray,
) -> None:
    expected_bits = expected.view(np.uint64)
    actual_bits = actual.view(np.uint64)
    mismatch = np.argwhere(expected_bits != actual_bits)
    if mismatch.size == 0:
        return

    row, column = (int(value) for value in mismatch[0])
    expected_bit = int(expected_bits[row, column])
    actual_bit = int(actual_bits[row, column])
    expected_value = float(expected[row, column])
    actual_value = float(actual[row, column])
    ulp_distance = abs(_ordered_uint64(expected_bit) - _ordered_uint64(actual_bit))
    raise AssertionError(
        f"case={case_name} array={array_name} coordinate=({row}, {column}) "
        f"expected={expected_value!r} actual={actual_value!r} "
        f"expected_uint64={expected_bit} actual_uint64={actual_bit} "
        f"absolute_difference={abs(expected_value - actual_value)!r} "
        f"ulp_distance={ulp_distance}"
    )


def test_kernel_inventory_is_exact() -> None:
    for radius, expected in _KERNEL_INVENTORY.items():
        specification = _median_background_kernel_spec(radius)
        assert (
            specification.kernel_resolution,
            specification.kernel_active_count,
            specification.rank_index,
            specification.rank_backend_reference,
        ) == expected


def test_kernel_resolution_is_two_radius_plus_one() -> None:
    for radius in _KERNEL_INVENTORY:
        assert _median_background_kernel_spec(radius).kernel_resolution == 2 * radius + 1


def test_kernel_active_count_is_odd() -> None:
    for radius in _KERNEL_INVENTORY:
        assert _median_background_kernel_spec(radius).kernel_active_count % 2 == 1


def test_kernel_rank_is_half_the_active_count() -> None:
    for radius in _KERNEL_INVENTORY:
        specification = _median_background_kernel_spec(radius)
        assert specification.rank_index == specification.kernel_active_count // 2


def test_kernel_backend_reference_uses_frozen_threshold() -> None:
    assert _median_background_kernel_spec(2).rank_backend_reference == "direct"
    assert _median_background_kernel_spec(3).rank_backend_reference == "radixtree"


def test_offsets_are_in_row_major_order() -> None:
    offsets = _median_background_active_offsets(20)
    keys = offsets[:, 0] * 10000 + offsets[:, 1]
    assert np.array_equal(keys, np.sort(keys))


def test_offsets_obey_the_inclusive_integer_ellipse_condition() -> None:
    radius = 20
    offsets = _median_background_active_offsets(radius)
    left = 4 * (offsets[:, 0] * offsets[:, 0] + offsets[:, 1] * offsets[:, 1])
    assert np.all(left <= (2 * radius + 1) ** 2)


def test_offsets_exclude_immediately_exterior_integer_positions() -> None:
    radius = 20
    offsets = _median_background_active_offsets(radius)
    radius_square = (2 * radius + 1) ** 2
    for dr in range(-radius, radius + 1):
        row_offsets = offsets[offsets[:, 0] == dr, 1]
        next_dc = int(np.max(np.abs(row_offsets))) + 1
        assert 4 * (dr * dr + next_dc * next_dc) > radius_square


def test_offsets_contain_the_central_pixel() -> None:
    offsets = _median_background_active_offsets(20)
    assert np.any(np.all(offsets == np.array([0, 0]), axis=1))


def test_offsets_are_c_contiguous_and_read_only() -> None:
    offsets = _median_background_active_offsets(20)
    assert offsets.flags.c_contiguous
    assert not offsets.flags.writeable


def test_offset_cache_preserves_content() -> None:
    first = _median_background_active_offsets(20)
    second = _median_background_active_offsets(np.int64(20))
    assert first is second
    assert np.array_equal(first, second)


@pytest.mark.parametrize(
    "radius",
    [True, 0, -1, 1025, 1.0, 1.5, "20"],
)
def test_radius_validation_rejects_values_outside_the_contract(radius: object) -> None:
    expected_error = TypeError if isinstance(radius, (bool, float, str)) else ValueError
    with pytest.raises(expected_error):
        _median_background_kernel_spec(radius)


@pytest.mark.parametrize(
    ("radius", "expected"),
    [
        (1, 1),
        (1024, 1024),
        (np.int8(2), 2),
        (np.int64(20), 20),
        (np.uint8(3), 3),
        (np.uint64(1024), 1024),
    ],
)
def test_radius_validation_accepts_python_and_numpy_integer_scalars(
    radius: object,
    expected: int,
) -> None:
    specification = _median_background_kernel_spec(radius)
    assert type(specification.radius_px) is int
    assert specification.radius_px == expected


@pytest.mark.parametrize(
    "radius",
    [
        True,
        False,
        np.bool_(True),
        np.bool_(False),
        np.array(2, dtype=np.int64),
        np.array(2, dtype=np.uint64),
        np.array(True),
        2.0,
        "2",
    ],
)
def test_radius_validation_rejects_non_integer_scalars_with_type_error(radius: object) -> None:
    with pytest.raises(TypeError, match="Python or NumPy integer scalar"):
        _median_background_kernel_spec(radius)


@pytest.mark.parametrize(
    "radius",
    [0, -1, 1025, 10**100, -(10**100), np.uint64(1025)],
)
def test_radius_validation_rejects_all_out_of_range_integers_with_value_error(
    radius: object,
) -> None:
    with pytest.raises(ValueError, match=r"1\.\.1024"):
        _median_background_kernel_spec(radius)


@pytest.mark.parametrize("radius", [True, False, np.bool_(True), np.bool_(False)])
def test_radius_validation_explains_that_booleans_are_invalid(radius: object) -> None:
    with pytest.raises(TypeError, match="booleans are not valid"):
        _median_background_kernel_spec(radius)


@pytest.mark.parametrize(
    "data, exception, message",
    [
        (np.array(1.0), ValueError, "two-dimensional"),
        (np.array([1.0, 2.0]), ValueError, "two-dimensional"),
        (np.ones((1, 1, 1)), ValueError, "two-dimensional"),
        (np.empty((0, 2)), ValueError, "non-empty"),
        (np.array([[np.nan]]), ValueError, "finite"),
        (np.array([[np.inf]]), ValueError, "finite"),
        (np.array([[-np.inf]]), ValueError, "finite"),
    ],
)
def test_input_validation_rejects_outside_the_frozen_domain(
    data: np.ndarray,
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        _gwyddion_median_background_result(data, 1)


def test_compatible_input_is_converted_to_float64() -> None:
    background, corrected, _ = _gwyddion_median_background_result([[1, 2], [3, 4]], 1)
    assert background.dtype == np.float64
    assert corrected.dtype == np.float64


def test_input_is_not_mutated() -> None:
    data = np.array([[1, -2, 3], [4, 5, -6]], dtype=np.float32)
    before = data.copy()
    _gwyddion_median_background_result(data, 2)
    assert np.array_equal(data, before)


def test_outputs_do_not_share_memory_with_input_or_each_other() -> None:
    data = np.arange(12, dtype=np.float64).reshape(3, 4)
    background, corrected, _ = _gwyddion_median_background_result(data, 1)
    assert not np.shares_memory(data, background)
    assert not np.shares_memory(data, corrected)
    assert not np.shares_memory(background, corrected)


def test_outputs_are_float64_two_dimensional_c_contiguous_and_finite() -> None:
    background, corrected, _ = _gwyddion_median_background_result([[1, 2], [3, 4]], 1)
    for output in (background, corrected):
        assert output.dtype == np.float64
        assert output.ndim == 2
        assert output.flags.c_contiguous
        assert np.all(np.isfinite(output))


def test_output_shape_is_preserved() -> None:
    data = np.arange(15, dtype=np.float64).reshape(3, 5)
    background, corrected, _ = _gwyddion_median_background_result(data, 2)
    assert background.shape == data.shape
    assert corrected.shape == data.shape


def test_border_extension_clamps_to_the_nearest_edge() -> None:
    data = np.array([[0.0, 10.0], [20.0, 30.0]])
    background, corrected, _ = _gwyddion_median_background_result(data, 1)
    assert background[0, 0] == 10.0
    assert corrected[0, 0] == -10.0


def test_constant_field_has_identity_background_and_zero_corrected() -> None:
    data = np.full((4, 5), 7.25, dtype=np.float64)
    background, corrected, _ = _gwyddion_median_background_result(data, 3)
    assert np.array_equal(background.view(np.uint64), data.view(np.uint64))
    assert np.array_equal(corrected.view(np.uint64), np.zeros_like(corrected).view(np.uint64))


def test_signed_field_produces_finite_reconstructable_outputs() -> None:
    data = np.array([[-4.0, -1.0, 2.0], [3.0, -5.0, 7.0]], dtype=np.float64)
    background, corrected, _ = _gwyddion_median_background_result(data, 2)
    assert np.all(np.isfinite(background))
    assert np.all(np.isfinite(corrected))
    np.testing.assert_allclose(data, background + corrected, atol=1e-15, rtol=0.0)


def test_positive_impulse_uses_the_rank_background() -> None:
    data = np.zeros((5, 5), dtype=np.float64)
    data[2, 2] = 100.0
    background, corrected, _ = _gwyddion_median_background_result(data, 1)
    assert np.array_equal(background.view(np.uint64), np.zeros_like(background).view(np.uint64))
    assert corrected[2, 2] == 100.0


def test_negative_impulse_uses_the_rank_background() -> None:
    data = np.zeros((5, 5), dtype=np.float64)
    data[2, 2] = -100.0
    background, corrected, _ = _gwyddion_median_background_result(data, 1)
    assert np.array_equal(background.view(np.uint64), np.zeros_like(background).view(np.uint64))
    assert corrected[2, 2] == -100.0


def test_singleton_one_by_one_field() -> None:
    data = np.array([[3.5]], dtype=np.float64)
    background, corrected, _ = _gwyddion_median_background_result(data, 1024)
    assert np.array_equal(background.view(np.uint64), data.view(np.uint64))
    assert np.array_equal(corrected.view(np.uint64), np.zeros_like(corrected).view(np.uint64))


def test_singleton_row_field() -> None:
    data = np.array([[2.0, -1.0, 5.0, 0.0]], dtype=np.float64)
    background, corrected, _ = _gwyddion_median_background_result(data, 3)
    assert background.shape == data.shape
    assert corrected.shape == data.shape


def test_singleton_column_field() -> None:
    data = np.array([[2.0], [-1.0], [5.0], [0.0]], dtype=np.float64)
    background, corrected, _ = _gwyddion_median_background_result(data, 3)
    assert background.shape == data.shape
    assert corrected.shape == data.shape


def test_all_fixture_backgrounds_are_bitwise_exact() -> None:
    manifest, arrays = _fixture()
    for case in manifest["cases"]:  # type: ignore[index]
        name = case["name"]
        background, _, _ = _result_for_case(name)
        _assert_bitwise_equal(name, "background", arrays[case["arrays"]["background"]], background)


def test_all_fixture_corrected_fields_are_bitwise_exact() -> None:
    manifest, arrays = _fixture()
    for case in manifest["cases"]:  # type: ignore[index]
        name = case["name"]
        _, corrected, _ = _result_for_case(name)
        _assert_bitwise_equal(name, "corrected", arrays[case["arrays"]["corrected"]], corrected)


def test_fixture_metadata_matches_the_private_kernel_specification() -> None:
    manifest, _ = _fixture()
    for case in manifest["cases"]:  # type: ignore[index]
        _, _, specification = _result_for_case(case["name"])
        assert specification.radius_px == case["radius"]
        assert specification.kernel_resolution == case["kernel_resolution"]
        assert specification.kernel_active_count == case["kernel_active_count"]
        assert specification.rank_index == case["rank_index"]
        assert specification.rank_backend_reference == case["rank_backend_reference"]


def test_fixture_results_obey_the_reconstruction_contract() -> None:
    manifest, arrays = _fixture()
    for case in manifest["cases"]:  # type: ignore[index]
        name = case["name"]
        background, corrected, _ = _result_for_case(name)
        np.testing.assert_allclose(
            arrays[case["arrays"]["input"]],
            background + corrected,
            atol=1e-15,
            rtol=0.0,
        )

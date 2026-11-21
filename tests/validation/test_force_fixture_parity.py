"""Regression tests for the frozen fixture comparison."""

import numpy as np
import pytest

from tests.validation.force_fixture_parity import assert_fixture_values


def test_regeneration_budget_is_in_ulps() -> None:
    frozen = np.array([1e-10, 1e-2])
    adjacent = np.nextafter(frozen, np.inf)
    assert_fixture_values(adjacent, frozen, "derived values", max_ulp=1)
    with pytest.raises(AssertionError, match="derived values"):
        assert_fixture_values(np.nextafter(adjacent, np.inf), frozen, "derived values", max_ulp=1)
    with pytest.raises(AssertionError, match="exact values"):
        assert_fixture_values(adjacent, frozen, "exact values")


@pytest.mark.parametrize(
    ("actual", "frozen"),
    [
        (np.array([1.0], dtype=np.float32), np.array([1.0])),
        (np.array([[1.0]]), np.array([1.0])),
        (np.array([-0.0]), np.array([0.0])),
        (np.array([np.nextafter(0.0, 1.0)]), np.array([0.0])),
        (np.array([np.inf]), np.array([np.finfo(float).max])),
        (np.array([1.0]), np.array([np.nan])),
    ],
)
def test_regeneration_budget_preserves_fixture_structure(actual, frozen) -> None:
    with pytest.raises(AssertionError, match="fixture contract"):
        assert_fixture_values(actual, frozen, "fixture contract", max_ulp=1)

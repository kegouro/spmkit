from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis._gwyddion_flat_disc_morphology import (
    Plan,
    _build_requirement,
    _gwyddion_flat_disc_kernel,
    _gwyddion_flat_disc_morphology_result,
    _segments,
    _validated_gwyddion_flat_disc_size,
)

FIXTURE = Path(__file__).resolve().parents[1] / "validation/fixtures/gwyddion/flat_disc_morphology"


def test_kernel_inventory_and_validation() -> None:
    assert [_gwyddion_flat_disc_kernel(size).kernel_active_count for size in range(2, 32)][0:4] == [
        4,
        9,
        12,
        21,
    ]
    assert _gwyddion_flat_disc_kernel(30).kernel_active_count == 716
    assert _gwyddion_flat_disc_kernel(31).kernel_active_count == 749
    assert isinstance(_validated_gwyddion_flat_disc_size(np.uint8(2)), int)
    for value in (True, np.array(2), 2.0, "2"):
        with pytest.raises(TypeError):
            _validated_gwyddion_flat_disc_size(value)
    for value in (1, 32, 10**100):
        with pytest.raises(ValueError):
            _validated_gwyddion_flat_disc_size(value)


def test_frozen_opening_and_closing_are_bitwise_exact() -> None:
    manifest = json.loads((FIXTURE / "flat_disc_morphology_reference.json").read_text())
    with np.load(FIXTURE / "flat_disc_morphology_reference.npz", allow_pickle=False) as archive:
        for case in manifest["cases"]:
            input_data = archive[case["input_key"]].copy(order="C")
            before = input_data.copy(order="C")
            for size in case["sizes"]:
                result = _gwyddion_flat_disc_morphology_result(input_data, size["size_px"])
                for operation in ("opening", "closing"):
                    expected = archive[size[f"{operation}_key"]]
                    actual = getattr(result, operation)
                    assert np.array_equal(actual.view(np.uint64), expected.view(np.uint64)), (
                        case["case_id"],
                        operation,
                        size["size_px"],
                    )
                    assert actual.dtype == np.float64 and actual.flags.c_contiguous
                assert not np.shares_memory(result.opening, result.closing)
            assert np.array_equal(input_data.view(np.uint64), before.view(np.uint64))


def test_input_contract() -> None:
    for value in (np.array([]), np.array([1.0]), np.zeros((1, 1, 1)), np.array([[np.nan]])):
        with pytest.raises(ValueError):
            _gwyddion_flat_disc_morphology_result(value, 2)


def _requirement_signature(plan: Plan) -> tuple[tuple[object, ...], ...]:
    rows: list[tuple[object, ...]] = []
    for kind, mapping in (("each", plan.each), ("even", plan.even)):
        for length, requirement in sorted(mapping.items()):
            rows.append(
                (
                    kind,
                    length,
                    requirement.needed,
                    requirement.sublen1,
                    requirement.sublen2,
                    requirement.even_odd,
                    requirement.even_even,
                )
            )
    return tuple(rows)


def test_requirement_tree_is_complete_and_deterministic() -> None:
    lengths = {int(segment[2]) for size_px in range(2, 32) for segment in _segments(size_px, False)}
    first = Plan()
    for length in sorted(lengths):
        _build_requirement(first, length, False)
    second = Plan()
    for length in sorted(lengths):
        _build_requirement(second, length, False)

    assert _requirement_signature(first) == _requirement_signature(second)
    for mapping in (first.each, first.even):
        for length, requirement in mapping.items():
            if not requirement.needed or length == 1:
                continue
            assert requirement.sublen1 > 0
            assert requirement.sublen2 > 0
            assert requirement.sublen1 + requirement.sublen2 == length


def test_singleton_and_thin_fields_execute_all_sizes() -> None:
    for shape in ((1, 1), (1, 7), (7, 1)):
        field = np.arange(np.prod(shape), dtype=np.float64).reshape(shape)
        for size_px in range(2, 32):
            result = _gwyddion_flat_disc_morphology_result(field, size_px)
            assert result.opening.shape == shape
            assert result.closing.shape == shape

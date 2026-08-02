"""Public-contract tests for Gwyddion 2.71 flat-disc morphology."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

import spmkit.core.analysis as analysis
import spmkit.core.analysis.background as background_module
from spmkit.core.analysis import (
    gwyddion_flat_disc_closing,
    gwyddion_flat_disc_opening,
)
from spmkit.core.models import SPMChannel

_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "flat_disc_morphology"
)
_FIXTURE_PATH = _FIXTURE_DIRECTORY / "flat_disc_morphology_reference.npz"
_MANIFEST_PATH = _FIXTURE_DIRECTORY / "flat_disc_morphology_reference.json"
_OPERATIONS: tuple[Callable[..., SPMChannel], ...] = (
    gwyddion_flat_disc_opening,
    gwyddion_flat_disc_closing,
)


def _manifest() -> dict[str, object]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="Flat-disc fixture",
        data=data,
        unit="V",
        x_range=8.5e-6,
        y_range=6.5e-6,
        direction="backward",
        group="Frozen morphology evidence",
        metadata={"source": "gwyddion-2.71-flat-disc", "context": {"id": 7}},
    )


def _ordered_uint64(bits: int) -> int:
    sign_bit = 1 << 63
    return ((~bits + 1) & ((1 << 64) - 1)) if bits & sign_bit else bits | sign_bit


def _assert_bitwise_equal(
    actual: np.ndarray,
    expected: np.ndarray,
    *,
    case_id: str,
    operation: str,
) -> None:
    actual_bits = actual.view(np.uint64)
    expected_bits = expected.view(np.uint64)
    if np.array_equal(actual_bits, expected_bits):
        return

    row, column = np.argwhere(actual_bits != expected_bits)[0]
    actual_bits_value = int(actual_bits[row, column])
    expected_bits_value = int(expected_bits[row, column])
    ulp_distance = abs(
        _ordered_uint64(actual_bits_value) - _ordered_uint64(expected_bits_value)
    )
    pytest.fail(
        f"case={case_id} operation={operation} coordinate=({row}, {column}) "
        f"expected={expected[row, column]!r} actual={actual[row, column]!r} "
        f"expected_uint64={expected_bits_value} actual_uint64={actual_bits_value} "
        f"absolute_difference={abs(actual[row, column] - expected[row, column])!r} "
        f"ulp_distance={ulp_distance}"
    )


def test_public_exports_signature_and_parameter_contract() -> None:
    expected_names = {"gwyddion_flat_disc_opening", "gwyddion_flat_disc_closing"}
    assert expected_names <= set(analysis.__all__)
    for name in expected_names:
        assert getattr(analysis, name) is not None

    for operation in _OPERATIONS:
        signature = inspect.signature(operation)
        assert list(signature.parameters) == ["channel", "size_px"]
        assert signature.parameters["size_px"].default == 5
        assert signature.parameters["size_px"].kind is inspect.Parameter.KEYWORD_ONLY
        assert "border" not in signature.parameters
        assert "shape" not in signature.parameters
        assert "rank" not in signature.parameters
        assert "backend" not in signature.parameters

    for private_name in (
        "_GwyddionFlatDiscKernelSpec",
        "_GwyddionFlatDiscMorphologyResult",
        "_gwyddion_flat_disc_kernel",
        "_gwyddion_flat_disc_extremum",
        "_gwyddion_flat_disc_morphology_result",
    ):
        assert private_name not in analysis.__all__
        assert not hasattr(analysis, private_name)


@pytest.mark.parametrize("case", _manifest()["cases"], ids=lambda case: case["case_id"])
def test_public_opening_and_closing_are_bitwise_exact(case: dict[str, object]) -> None:
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        source_data = np.array(archive[case["input_key"]], dtype=np.float64, order="C", copy=True)
        original_bits = source_data.view(np.uint64).copy()
        source = _channel(source_data)
        for size_entry in case["sizes"]:
            size_px = size_entry["size_px"]
            opening = gwyddion_flat_disc_opening(source, size_px=size_px)
            closing = gwyddion_flat_disc_closing(source, size_px=size_px)
            _assert_bitwise_equal(
                opening.data,
                archive[size_entry["opening_key"]],
                case_id=case["case_id"],
                operation="opening",
            )
            _assert_bitwise_equal(
                closing.data,
                archive[size_entry["closing_key"]],
                case_id=case["case_id"],
                operation="closing",
            )
            for output in (opening, closing):
                assert output.data.dtype == np.float64
                assert output.data.flags.c_contiguous
                assert output.data.shape == source.data.shape
                assert np.isfinite(output.data).all()
                assert not np.shares_memory(output.data, source.data)
            assert not np.shares_memory(opening.data, closing.data)
        assert np.array_equal(source.data.view(np.uint64), original_bits)


def test_context_and_metadata_are_preserved_without_sharing() -> None:
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        source = _channel(np.array(archive["input__wide_large_gradient"], copy=True, order="C"))
    opening = gwyddion_flat_disc_opening(source, size_px=3)
    closing = gwyddion_flat_disc_closing(source, size_px=3)
    for output in (opening, closing):
        assert output.name == source.name
        assert output.unit == source.unit
        assert output.x_range == source.x_range
        assert output.y_range == source.y_range
        assert output.direction == source.direction
        assert output.group == source.group
        assert output.metadata == source.metadata
        assert output.metadata is not source.metadata
    opening.metadata["new_key"] = True
    assert "new_key" not in source.metadata
    assert "new_key" not in closing.metadata


@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize("size_px", [True, np.array(2), 0, 32, 10**100, 2.0, "2"])
def test_validation_is_delegated(operation: Callable[..., SPMChannel], size_px: object) -> None:
    data = np.ones((3, 4), dtype=np.float64)
    expected = TypeError if isinstance(size_px, (bool, np.ndarray, float, str)) else ValueError
    with pytest.raises(expected):
        operation(_channel(data), size_px=size_px)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_nonfinite_data_is_rejected(operation: Callable[..., SPMChannel]) -> None:
    data = np.ones((2, 3), dtype=np.float64)
    data[0, 1] = np.nan
    with pytest.raises(ValueError, match="finite"):
        operation(_channel(data), size_px=3)


@pytest.mark.parametrize("operation", _OPERATIONS)
def test_each_public_call_invokes_private_entry_once(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[..., SPMChannel],
) -> None:
    calls = 0
    original = background_module._gwyddion_flat_disc_morphology_result

    def counted_entry(data: object, size_px: object) -> object:
        nonlocal calls
        calls += 1
        return original(data, size_px)

    monkeypatch.setattr(background_module, "_gwyddion_flat_disc_morphology_result", counted_entry)
    operation(_channel(np.arange(12, dtype=np.float64).reshape(3, 4)), size_px=4)
    assert calls == 1

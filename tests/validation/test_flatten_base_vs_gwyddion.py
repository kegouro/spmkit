from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import _flatten_base

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / "flatten_base"
_METADATA_PATH = _FIXTURE_DIR / "gwyddion_2_71_end_to_end.json"


def test_flatten_base_matches_gwyddion_2_71_end_to_end() -> None:
    metadata = json.loads(_METADATA_PATH.read_text())
    npz_path = _FIXTURE_DIR / metadata["artifacts"]["npz_filename"]

    assert hashlib.sha256(npz_path.read_bytes()).hexdigest() == (
        metadata["artifacts"]["npz_sha256"]
    )

    with np.load(npz_path) as fixture:
        input_field = np.asarray(
            fixture["input"],
            dtype=float,
        )
        expected_corrected = np.asarray(
            fixture["corrected"],
            dtype=float,
        )

    original_input = input_field.copy()
    field = metadata["field"]
    expected_flow = metadata["expected_control_flow"]
    expected_result = metadata["expected_result"]
    acceptance = metadata["acceptance"]

    result = _flatten_base._run_flatten_base(
        input_field,
        pixel_size_x=float(field["pixel_size_x"]),
        pixel_size_y=float(field["pixel_size_y"]),
    )

    attempted_degrees = tuple(iteration.degree for iteration in result.polynomial_stage.iterations)
    applied_degrees = tuple(
        iteration.degree for iteration in result.polynomial_stage.iterations if iteration.applied
    )
    expected_degrees = tuple(expected_flow["polynomial_degrees"])

    assert len(result.facet_stage.iterations) == (expected_flow["facet_iterations"])
    assert attempted_degrees == expected_degrees
    assert applied_degrees == expected_degrees
    assert result.final_peak.success is (expected_flow["final_peak_success"])

    assert result.final_peak.mean == pytest.approx(
        expected_result["final_peak_mean"],
        abs=acceptance["final_peak_mean_abs_error"],
        rel=0.0,
    )
    assert result.final_peak.rms == pytest.approx(
        expected_result["final_peak_rms"],
        abs=acceptance["final_peak_rms_abs_error"],
        rel=0.0,
    )

    np.testing.assert_allclose(
        result.corrected,
        expected_corrected,
        atol=acceptance["corrected_max_abs_error"],
        rtol=0.0,
    )

    assert float(np.min(result.corrected)) == pytest.approx(
        expected_result["corrected_minimum"],
        abs=acceptance["corrected_max_abs_error"],
        rel=0.0,
    )
    assert float(np.max(result.corrected)) == pytest.approx(
        expected_result["corrected_maximum"],
        abs=acceptance["corrected_max_abs_error"],
        rel=0.0,
    )

    np.testing.assert_array_equal(
        input_field,
        original_input,
    )
    np.testing.assert_allclose(
        result.corrected + result.background,
        input_field,
        atol=5e-14,
        rtol=0.0,
    )

    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable

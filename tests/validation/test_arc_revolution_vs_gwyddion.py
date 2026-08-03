from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis._gwyddion_arc_revolution import (
    _gwyddion_arc_background,
    _gwyddion_arc_corrected,
)

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / "arc_revolution"
_METADATA_PATH = _FIXTURE_DIR / "gwyddion_2_71_directional.json"
_METADATA = json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
_CASE_NAMES = tuple(_METADATA["cases"])


def _canonical_array_sha256(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(
        array,
        dtype=np.float64,
    )

    digest = hashlib.sha256()
    digest.update(str(canonical.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(value) for value in canonical.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _load_fixture() -> dict[str, np.ndarray]:
    npz_path = _FIXTURE_DIR / _METADATA["artifacts"]["npz_filename"]

    assert hashlib.sha256(npz_path.read_bytes()).hexdigest() == (
        _METADATA["artifacts"]["npz_sha256"]
    )

    with np.load(npz_path) as fixture:
        arrays = {
            name: np.asarray(
                fixture[name],
                dtype=np.float64,
            )
            for name in fixture.files
        }

    expected_hashes = _METADATA["artifacts"]["array_canonical_sha256"]

    assert set(arrays) == set(expected_hashes)

    for name, array in arrays.items():
        assert _canonical_array_sha256(array) == expected_hashes[name]

    return arrays


@pytest.mark.parametrize("case_name", _CASE_NAMES)
def test_arc_background_matches_gwyddion_2_71(
    case_name: str,
) -> None:
    fixture = _load_fixture()
    case = _METADATA["cases"][case_name]
    acceptance = _METADATA["acceptance"]

    input_field = fixture["input"].copy()
    original_input = input_field.copy()

    result = _gwyddion_arc_background(
        input_field,
        _METADATA["parameters"]["radius_px"],
        direction=case["direction"],
        inverted=case["inverted"],
    )

    np.testing.assert_allclose(
        result,
        fixture[f"background_{case_name}"],
        atol=acceptance["background_max_abs_error"],
        rtol=0.0,
    )
    np.testing.assert_array_equal(
        input_field,
        original_input,
    )

    assert result.dtype == np.float64
    assert result.flags.c_contiguous
    assert not result.flags.writeable


@pytest.mark.parametrize(
    "case_name",
    [name for name, case in _METADATA["cases"].items() if case["corrected_reference_valid"]],
)
def test_arc_corrected_matches_valid_gwyddion_2_71_results(
    case_name: str,
) -> None:
    fixture = _load_fixture()
    case = _METADATA["cases"][case_name]
    acceptance = _METADATA["acceptance"]

    input_field = fixture["input"].copy()

    background = _gwyddion_arc_background(
        input_field,
        _METADATA["parameters"]["radius_px"],
        direction=case["direction"],
        inverted=case["inverted"],
    )
    corrected = _gwyddion_arc_corrected(
        input_field,
        _METADATA["parameters"]["radius_px"],
        direction=case["direction"],
        inverted=case["inverted"],
    )

    np.testing.assert_allclose(
        corrected,
        fixture[f"corrected_{case_name}"],
        atol=acceptance["corrected_max_abs_error"],
        rtol=0.0,
    )
    np.testing.assert_allclose(
        corrected + background,
        input_field,
        atol=acceptance["reconstruction_max_abs_error"],
        rtol=0.0,
    )

    assert not corrected.flags.writeable


def test_horizontal_inverted_reference_defect_is_preserved_and_repaired() -> None:
    fixture = _load_fixture()
    defect = _METADATA["known_reference_defects"]["horizontal_inverted_corrected_result"]
    acceptance = _METADATA["acceptance"]

    input_field = fixture["input"].copy()
    reference_corrected = fixture["corrected_horizontal_inverted"]

    assert defect["classification"] == "KNOWN_REFERENCE_DEFECT"
    assert defect["reference_result_untouched"] is True
    assert np.all(reference_corrected == defect["sentinel"])

    background = _gwyddion_arc_background(
        input_field,
        _METADATA["parameters"]["radius_px"],
        direction="horizontal",
        inverted=True,
    )
    corrected = _gwyddion_arc_corrected(
        input_field,
        _METADATA["parameters"]["radius_px"],
        direction="horizontal",
        inverted=True,
    )

    np.testing.assert_allclose(
        background,
        fixture["background_horizontal_inverted"],
        atol=acceptance["background_max_abs_error"],
        rtol=0.0,
    )
    np.testing.assert_allclose(
        corrected + background,
        input_field,
        atol=acceptance["reconstruction_max_abs_error"],
        rtol=0.0,
    )

    assert not np.any(corrected == defect["sentinel"])
    assert not background.flags.writeable
    assert not corrected.flags.writeable


@pytest.mark.parametrize("case_name", _CASE_NAMES)
def test_public_arc_result_matches_gwyddion_2_71(
    case_name: str,
) -> None:
    from spmkit.core.analysis import (
        analyze_gwyddion_arc_revolution_background,
    )
    from spmkit.core.models import SPMChannel

    fixture = _load_fixture()
    case = _METADATA["cases"][case_name]
    field = _METADATA["field"]
    acceptance = _METADATA["acceptance"]

    input_field = fixture["input"].copy()
    original_input = input_field.copy()

    channel = SPMChannel(
        name="Gwyddion 2.71 frozen Revolve Arc field",
        data=input_field,
        unit="V",
        x_range=float(field["xreal"]),
        y_range=float(field["yreal"]),
        direction="forward",
        group="external-validation",
        metadata={
            "fixture_id": _METADATA["fixture_id"],
            "reference": "Gwyddion 2.71",
        },
    )

    result = analyze_gwyddion_arc_revolution_background(
        channel,
        _METADATA["parameters"]["radius_px"],
        direction=case["direction"],
        inverted=case["inverted"],
    )

    np.testing.assert_allclose(
        result.background.data,
        fixture[f"background_{case_name}"],
        atol=acceptance["background_max_abs_error"],
        rtol=0.0,
    )

    if case["corrected_reference_valid"]:
        np.testing.assert_allclose(
            result.corrected.data,
            fixture[f"corrected_{case_name}"],
            atol=acceptance["corrected_max_abs_error"],
            rtol=0.0,
        )
    else:
        defect = _METADATA["known_reference_defects"]["horizontal_inverted_corrected_result"]
        assert np.all(fixture[f"corrected_{case_name}"] == defect["sentinel"])
        assert not np.any(result.corrected.data == defect["sentinel"])

    np.testing.assert_allclose(
        result.corrected.data + result.background.data,
        input_field,
        atol=acceptance["reconstruction_max_abs_error"],
        rtol=0.0,
    )
    np.testing.assert_array_equal(
        input_field,
        original_input,
    )

    assert result.method == "gwyddion_arc_revolution"
    assert result.parameters == {
        "radius_px": 2.5,
        "direction": case["direction"],
        "inverted": case["inverted"],
    }
    assert result.background.unit == "V"
    assert result.corrected.unit == "V"
    assert not result.background.data.flags.writeable
    assert not result.corrected.data.flags.writeable

"""Validation tests for SPMKit Gwyddion Sphere Revolution against frozen 2.71 fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import (
    BackgroundResult,
    analyze_gwyddion_sphere_revolution_background,
)
from spmkit.core.analysis._gwyddion_sphere_revolution import (
    _gwyddion_sphere_background,
    _gwyddion_sphere_result,
)
from spmkit.core.models import SPMChannel

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gwyddion" / "sphere_revolution"
_NPZ_PATH = _FIXTURE_DIR / "sphere_revolution_reference.npz"
_JSON_PATH = _FIXTURE_DIR / "sphere_revolution_reference.json"

with _JSON_PATH.open("r", encoding="utf-8") as _f:
    _METADATA = json.load(_f)

_ACCEPTANCE_ATOL = float(_METADATA["acceptance"]["background_atol"])
_ACCEPTANCE_RTOL = float(_METADATA["acceptance"]["rtol"])


def _canonical_array_sha256(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(str(canonical.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(value) for value in canonical.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def test_sphere_fixture_metadata_and_artifact_hashes() -> None:
    assert _METADATA["schema_version"] == 2
    assert _METADATA["reference_software"] == "Gwyddion"
    assert _METADATA["reference_version"] == "2.71"
    assert _METADATA["operation"] == "sphere-revolve"
    assert _METADATA["spmkit_method"] == "gwyddion_sphere_revolution"
    assert _METADATA["branch"] == "feat/gwyddion-leveling-parity"
    assert _METADATA["head"] == "c693fc97e94a5829f57c8b2acf8f522f4f05fb4f"
    assert len(_METADATA["case_order"]) == 10

    npz_sha256 = hashlib.sha256(_NPZ_PATH.read_bytes()).hexdigest()
    assert npz_sha256 == _METADATA["npz_sha256"]

    source_hashes = _METADATA["source_and_artifact_hashes"]
    expected_sources = {
        "sphere_revolve_c": "4218cd4e303634c610e9be5f18656d12715c68df95a9b30930b33232b3d8cbe9",
        "probe_c": "97248b51df742937ed5dc0a975b8b1ca08b1b6eeb5add95eda4526118337b188",
        "runner_sh": "d673393126833277bda41c77403f1dbaf5dc965d6d8b63ee73994238bec8f7a7",
        "oracle_py": "f1598e5f7cd0e173ec72ea928e270038ac8ab5f4c61d57b31a60373e50d40e4b",
        "precision_audit_py": "58f1acd0d3c3d644c93adcc7c754889e883726976341695e974d4c09a34f72e4",
        "normative_spec_md": "3db2e7ea0c965dfa9bcd803ade6d3dae2fc38b216a132c05df36d52a9256b1c8",
        "kernel_py": "ef00ec0033de3966ff1ab7642fdba3f24e0d9030550e5c7995fb55318eb75a38",
        "core_test_py": "d0a46f20d6260327f80d68ddae8bfa5360def162b6ca6db77511baf5df5e6ef5",
    }
    for k, v in expected_sources.items():
        assert source_hashes[k] == v


def test_sphere_fixture_canonical_array_hashes() -> None:
    expected_hashes = _METADATA["canonical_array_hashes"]
    npz_data = np.load(_NPZ_PATH)

    assert len(npz_data.files) == 80
    assert len(expected_hashes) == 80
    assert set(npz_data.files) == set(expected_hashes.keys())

    for array_name in npz_data.files:
        array = npz_data[array_name]
        assert array.dtype == np.float64
        assert array.flags.c_contiguous
        assert np.all(np.isfinite(array))
        assert _canonical_array_sha256(array) == expected_hashes[array_name]


def test_gwyddion_sphere_direct_normal_background() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        inp = npz_data[f"input__{pair_id}"]
        expected_bg = npz_data[f"direct_background__{pair_id}"]

        inp_copy = inp.copy()
        bg = _gwyddion_sphere_background(inp, radius)

        assert bg.dtype == np.float64
        assert bg.flags.c_contiguous
        assert not bg.flags.writeable
        np.testing.assert_array_equal(inp, inp_copy)

        np.testing.assert_allclose(
            bg,
            expected_bg,
            atol=_ACCEPTANCE_ATOL,
            rtol=_ACCEPTANCE_RTOL,
        )


def test_gwyddion_sphere_direct_normal_corrected() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        inp = npz_data[f"input__{pair_id}"]
        expected_corr = npz_data[f"direct_corrected__{pair_id}"]

        inp_copy = inp.copy()
        _, corr = _gwyddion_sphere_result(inp, radius, inverted=False)

        assert corr.dtype == np.float64
        assert corr.flags.c_contiguous
        assert not corr.flags.writeable
        np.testing.assert_array_equal(inp, inp_copy)

        np.testing.assert_allclose(
            corr,
            expected_corr,
            atol=_ACCEPTANCE_ATOL,
            rtol=_ACCEPTANCE_RTOL,
        )


def test_gwyddion_sphere_normal_on_negated_input() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        neg_inp = npz_data[f"negated_input__{pair_id}"]
        expected_neg_bg = npz_data[f"direct_negated_background__{pair_id}"]

        neg_bg = _gwyddion_sphere_background(neg_inp, radius)

        np.testing.assert_allclose(
            neg_bg,
            expected_neg_bg,
            atol=_ACCEPTANCE_ATOL,
            rtol=_ACCEPTANCE_RTOL,
        )


def test_gwyddion_sphere_derived_inverted_background() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        inp = npz_data[f"input__{pair_id}"]
        expected_inv_bg = npz_data[f"derived_inverted_background__{pair_id}"]

        inv_bg, _ = _gwyddion_sphere_result(inp, radius, inverted=True)

        assert inv_bg.dtype == np.float64
        assert inv_bg.flags.c_contiguous
        assert not inv_bg.flags.writeable

        np.testing.assert_allclose(
            inv_bg,
            expected_inv_bg,
            atol=_ACCEPTANCE_ATOL,
            rtol=_ACCEPTANCE_RTOL,
        )


def test_gwyddion_sphere_safe_inverted_corrected() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        inp = npz_data[f"input__{pair_id}"]
        expected_safe_corr = npz_data[f"safe_inverted_corrected__{pair_id}"]

        _, inv_corr = _gwyddion_sphere_result(inp, radius, inverted=True)

        assert inv_corr.dtype == np.float64
        assert inv_corr.flags.c_contiguous
        assert not inv_corr.flags.writeable

        np.testing.assert_allclose(
            inv_corr,
            expected_safe_corr,
            atol=_ACCEPTANCE_ATOL,
            rtol=_ACCEPTANCE_RTOL,
        )


def test_gwyddion_sphere_reconstruction() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])

        inp = npz_data[f"input__{pair_id}"]
        neg_inp = npz_data[f"negated_input__{pair_id}"]

        # 1. Normal route
        bg, corr = _gwyddion_sphere_result(inp, radius, inverted=False)
        np.testing.assert_allclose(corr + bg, inp, atol=_ACCEPTANCE_ATOL, rtol=0.0)

        # 2. Negated normal route
        neg_bg, neg_corr = _gwyddion_sphere_result(neg_inp, radius, inverted=False)
        np.testing.assert_allclose(neg_corr + neg_bg, neg_inp, atol=_ACCEPTANCE_ATOL, rtol=0.0)

        # 3. Inverted route
        inv_bg, inv_corr = _gwyddion_sphere_result(inp, radius, inverted=True)
        np.testing.assert_allclose(inv_corr + inv_bg, inp, atol=_ACCEPTANCE_ATOL, rtol=0.0)


def test_gwyddion_sphere_frozen_inverted_failure_evidence() -> None:
    inv_failures = _METADATA["inverted_reference_failures"]

    assert len(inv_failures) == 15

    for failure in inv_failures:
        assert failure["arrays_available"] is False
        assert failure["execute_started"] is True
        assert failure["execute_returned"] is False
        assert failure["normal_exit_code"] != 0
        assert failure["asan_exit_code"] != 0


def test_gwyddion_sphere_public_analyze_against_fixture() -> None:
    npz_data = np.load(_NPZ_PATH)
    cases = _METADATA["cases"]

    for pair_id in _METADATA["case_order"]:
        case_info = cases[pair_id]
        radius = float(case_info["radius"])
        inp = npz_data[f"input__{pair_id}"]

        channel = SPMChannel(
            name=f"Channel_{pair_id}",
            data=inp,
            unit="nm",
            x_range=1.0e-6,
            y_range=1.0e-6,
            metadata={"pair_id": pair_id},
        )

        for inv in (False, True):
            res = analyze_gwyddion_sphere_revolution_background(
                channel,
                radius,
                inverted=inv,
            )

            assert isinstance(res, BackgroundResult)
            assert res.method == "gwyddion_sphere_revolution"
            assert res.parameters == {"radius_px": radius, "inverted": inv}

            assert res.background.unit == "nm"
            assert res.background.x_range == 1.0e-6
            assert res.background.y_range == 1.0e-6
            assert res.background.metadata == {"pair_id": pair_id}

            assert res.corrected.unit == "nm"
            assert res.corrected.x_range == 1.0e-6
            assert res.corrected.y_range == 1.0e-6
            assert res.corrected.metadata == {"pair_id": pair_id}

            if not inv:
                expected_bg = npz_data[f"direct_background__{pair_id}"]
                expected_corr = npz_data[f"direct_corrected__{pair_id}"]
            else:
                expected_bg = npz_data[f"derived_inverted_background__{pair_id}"]
                expected_corr = npz_data[f"safe_inverted_corrected__{pair_id}"]

            np.testing.assert_allclose(
                res.background.data,
                expected_bg,
                atol=_ACCEPTANCE_ATOL,
                rtol=_ACCEPTANCE_RTOL,
            )
            np.testing.assert_allclose(
                res.corrected.data,
                expected_corr,
                atol=_ACCEPTANCE_ATOL,
                rtol=_ACCEPTANCE_RTOL,
            )

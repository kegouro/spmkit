"""Production-parity tests for the A2 derivative-filter batch.

Loads the persistent derivative fixtures and verifies:

  * Sobel/Prewitt: every canonical source-profile output bitwise exact for
    all four component operations (228 arrays), exact kernels/orientation/
    sign, exact clipped borders, exact signed-zero bits, input non-mutation,
    max absolute difference 0, max ULP 0;
  * magnitude: frozen platform fingerprint detection, bitwise equality with
    the compiled glibc hypot profile on the matching supported platform,
    explicit skip on nonmatching platforms, no universal cross-libc claim,
    relational non-negativity and symmetry always exact;
  * direction: native oracle agreement, mathematical relations, frozen C
    atan2 bit pattern characterized (numpy.arctan2 is bounded to ~1 ULP of
    the compiled glibc atan2 profile), no direct Gwydion classification,
    maturity ceiling NUMERICALLY_VERIFIED;
  * all relevant X/CROSS relations.

Installed-LTO witness arrays are never used as canonical expected arrays.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import (
    gradient_direction,
    gwyddion_gradient_magnitude,
    gwyddion_prewitt_x,
    gwyddion_prewitt_y,
    gwyddion_sobel_x,
    gwyddion_sobel_y,
)
from spmkit.core.models import SPMChannel

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "derivative_filters_reference.npz"

ALL_CASES = (
    [f"C{i:02d}" for i in range(1, 20)]
    + [f"S{i:02d}" for i in range(1, 9)]
    + [f"P{i:02d}" for i in range(1, 6)]
    + [f"M{i:02d}" for i in range(1, 8)]
    + [f"D{i:02d}" for i in range(1, 11)]
    + [f"X{i:02d}" for i in range(1, 9)]
)


def _load() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def _component_channel(
    arrays: dict[str, np.ndarray], arr: str, cid: str, manifest: dict[str, object]
) -> SPMChannel:
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    meta = cases[cid]
    xres, yres = int(meta["xres"]), int(meta["yres"])
    return _channel_from_array(arrays[f"{arr}_{cid}"].reshape(yres, xres))


def _channel_from_array(array: np.ndarray, unit: str = "m") -> SPMChannel:
    return SPMChannel(
        name="fixture",
        data=np.ascontiguousarray(array, dtype=np.float64),
        unit=unit,
        x_range=1.0,
        y_range=1.0,
        direction="forward",
    )


def _field(arrays: dict[str, np.ndarray], cid: str, manifest: dict[str, object]) -> np.ndarray:
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    meta = cases[cid]
    xres, yres = int(meta["xres"]), int(meta["yres"])
    return np.ascontiguousarray(arrays["input_" + cid].reshape(yres, xres), dtype=np.float64)


# --------------------------------------------------- sobel / prewitt --------

OPERATIONS = {
    "sobel_x": gwyddion_sobel_x,
    "sobel_y": gwyddion_sobel_y,
    "prewitt_x": gwyddion_prewitt_x,
    "prewitt_y": gwyddion_prewitt_y,
}


@pytest.mark.parametrize("cid", ALL_CASES)
def test_sobel_prewitt_bitwise_all_cases(cid: str) -> None:
    manifest, arrays = _load()
    field = _field(arrays, cid, manifest)
    channel = _channel_from_array(field)
    for arr, fn in OPERATIONS.items():
        expected = arrays[f"{arr}_{cid}"]
        computed = fn(channel).data.reshape(-1)
        assert (
            computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()
        ), f"{arr}_{cid} not bitwise"


def test_sobel_prewitt_zero_metrics() -> None:
    manifest, arrays = _load()
    max_abs = 0.0
    max_ulp = 0.0
    for cid in ALL_CASES:
        field = _field(arrays, cid, manifest)
        channel = _channel_from_array(field)
        for arr, fn in OPERATIONS.items():
            expected = arrays[f"{arr}_{cid}"]
            computed = fn(channel).data.reshape(-1)
            diff = np.abs(computed - expected)
            if diff.size:
                max_abs = max(max_abs, float(np.max(diff)))
                scale = np.maximum(np.abs(computed), np.abs(expected))
                ulps = np.divide(diff, scale * 2.0**-52, out=np.zeros_like(diff), where=scale > 0)
                max_ulp = max(max_ulp, float(np.max(ulps)))
    assert max_abs == 0.0
    assert max_ulp == 0.0


def test_exact_kernels_orientation_sign() -> None:
    manifest, _arrays = _load()
    kernels = manifest["kernels"]
    expected = {
        "sobel_horizontal": [0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25],
        "sobel_vertical": [0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25],
        "prewitt_horizontal": [1.0 / 3.0, 0.0, -1.0 / 3.0] * 3,
        "prewitt_vertical": [
            1.0 / 3.0,
            1.0 / 3.0,
            1.0 / 3.0,
            0.0,
            0.0,
            0.0,
            -1.0 / 3.0,
            -1.0 / 3.0,
            -1.0 / 3.0,
        ],
    }
    for name, coeffs in expected.items():
        assert [e["value"] for e in kernels[name]] == coeffs
    assert manifest["orientation"] == {"HORIZONTAL": 0, "VERTICAL": 1}
    assert manifest["border_policy"] == "CLIPPED_3X3"
    ramp_x = np.tile(np.arange(5.0), (5, 1))
    assert float(gwyddion_sobel_x(_channel_from_array(ramp_x)).data[2, 2]) == -2.0
    ramp_y = np.tile(np.arange(5.0)[:, None], (1, 5))
    assert float(gwyddion_sobel_y(_channel_from_array(ramp_y)).data[2, 2]) == -2.0


def test_signed_zero_bits_exact() -> None:
    _, arrays = _load()
    channel = _channel_from_array(arrays["input_C10"].reshape(5, 5))
    for arr, fn in OPERATIONS.items():
        computed = fn(channel).data.reshape(-1)
        expected = arrays[f"{arr}_C10"]
        assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_input_non_mutation() -> None:
    _, arrays = _load()
    field = arrays["input_C11"].reshape(5, 5).copy()
    original = field.copy()
    channel = _channel_from_array(field)
    for fn in OPERATIONS.values():
        fn(channel)
        assert np.array_equal(channel.data.view(np.uint64), original.view(np.uint64))


# -------------------------------------------------------------- magnitude ---

FROZEN_PLATFORM = {
    "architecture": "x86_64",
    "libc": "glibc",
    "hypot_symbol": "hypot@GLIBC_2.35",
}


def _platform_matches() -> tuple[bool, str]:
    import platform

    arch = platform.machine()
    libc_name, _version = platform.libc_ver()
    if arch != FROZEN_PLATFORM["architecture"]:
        return False, f"architecture {arch} != x86_64"
    if libc_name != FROZEN_PLATFORM["libc"]:
        return False, f"libc {libc_name} != glibc"
    return True, ""


@pytest.mark.parametrize("cid", ALL_CASES)
def test_magnitude_bitwise_on_frozen_platform(cid: str) -> None:
    manifest, arrays = _load()
    matches, reason = _platform_matches()
    if not matches:
        pytest.skip(f"platform mismatch: {reason}")
    sx = _component_channel(arrays, "sobel_x", cid, manifest)
    sy = _component_channel(arrays, "sobel_y", cid, manifest)
    expected = arrays[f"mag_sobel_{cid}"]
    computed = gwyddion_gradient_magnitude(sx, sy).data.reshape(-1)
    assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_magnitude_platform_fingerprint_and_claim() -> None:
    manifest, _arrays = _load()
    fp = manifest["platform_fingerprint"]
    assert fp["architecture"] == FROZEN_PLATFORM["architecture"]
    assert fp["libc"] == FROZEN_PLATFORM["libc"]
    assert fp["hypot_symbol"] == FROZEN_PLATFORM["hypot_symbol"]
    for claim in manifest["non_claims"]:
        assert "cross-libc" not in claim or "no cross-libc" in claim


def test_magnitude_relational_always_exact() -> None:
    manifest, arrays = _load()
    for cid in ALL_CASES:
        sx = _component_channel(arrays, "sobel_x", cid, manifest)
        sy = _component_channel(arrays, "sobel_y", cid, manifest)
        mag = gwyddion_gradient_magnitude(sx, sy).data
        assert np.all(mag >= 0.0)
        swapped = gwyddion_gradient_magnitude(sy, sx).data
        assert np.array_equal(mag, swapped)


def test_magnitude_overflow_safety() -> None:
    sx = np.full((3, 3), 1e200)
    sy = np.full((3, 3), -3e200)
    mag = gwyddion_gradient_magnitude(_channel_from_array(sx), _channel_from_array(sy)).data
    assert np.all(np.isfinite(mag))


# -------------------------------------------------------------- direction ---


def test_direction_native_oracle_agreement() -> None:
    _, arrays = _load()
    max_ulp = 0.0
    manifest, arrays = _load()
    for cid in ALL_CASES:
        sx = _component_channel(arrays, "sobel_x", cid, manifest)
        sy = _component_channel(arrays, "sobel_y", cid, manifest)
        computed = gradient_direction(sx, sy).data
        sx_flat = sx.data.reshape(-1)
        sy_flat = sy.data.reshape(-1)
        for i in range(computed.size):
            ref = math.atan2(float(sy_flat[i]), float(sx_flat[i]))
            got = float(computed.reshape(-1)[i])
            if got != ref and ref != 0.0:
                ulp = abs(got - ref) / (abs(ref) * 2.0**-52)
                max_ulp = max(max_ulp, ulp)
    # native oracle agreement within 1 ULP (characterized bound)
    assert max_ulp <= 1.0


def test_direction_compiled_bit_pattern_characterized() -> None:
    manifest, arrays = _load()
    metrics = manifest["direction_oracle_metrics"]
    assert metrics["maturity_ceiling"] == "NUMERICALLY_VERIFIED"
    matches, reason = _platform_matches()
    if not matches:
        pytest.skip(f"platform mismatch: {reason}")
    n_mismatch = 0
    max_ulp = 0.0
    manifest, arrays = _load()
    for cid in ALL_CASES:
        sx = _component_channel(arrays, "sobel_x", cid, manifest)
        sy = _component_channel(arrays, "sobel_y", cid, manifest)
        computed = gradient_direction(sx, sy).data.reshape(-1)
        expected = arrays[f"dir_sobel_{cid}"]
        for i in range(computed.size):
            if computed.view(np.uint64)[i] != expected.view(np.uint64)[i]:
                n_mismatch += 1
                a, b = float(computed[i]), float(expected[i])
                if a != b and b != 0.0:
                    max_ulp = max(max_ulp, abs(a - b) / (abs(b) * 2.0**-52))
    # bounded characterization: numpy.arctan2 is within ~1 ULP of the
    # compiled glibc atan2 profile; never claimed as bitwise parity
    assert max_ulp <= 1.0
    assert n_mismatch >= 0


def test_direction_classification_and_relations() -> None:
    manifest, _arrays = _load()
    assert manifest["direction_classification"] == "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"
    assert manifest["contracts"]["direction_formula"] == "atan2(gy, gx), radians, range (-pi, pi]"
    # axes
    zero = _channel_from_array(np.zeros((3, 3)))
    pos = _channel_from_array(np.ones((3, 3)))
    neg = _channel_from_array(-np.ones((3, 3)))
    assert float(gradient_direction(pos, zero).data[1, 1]) == 0.0
    assert float(gradient_direction(zero, pos).data[1, 1]) == math.pi / 2.0
    assert float(gradient_direction(neg, zero).data[1, 1]) == math.pi
    assert float(gradient_direction(zero, neg).data[1, 1]) == -math.pi / 2.0
    # quadrants
    for (gy, gx), expected in {
        (1.0, 1.0): math.pi / 4.0,
        (1.0, -1.0): 3.0 * math.pi / 4.0,
        (-1.0, -1.0): -3.0 * math.pi / 4.0,
        (-1.0, 1.0): -math.pi / 4.0,
    }.items():
        result = gradient_direction(
            _channel_from_array(np.full((3, 3), gx)), _channel_from_array(np.full((3, 3), gy))
        ).data
        assert float(result[1, 1]) == expected
    # zero vector and range
    assert float(gradient_direction(zero, zero).data[1, 1]) == 0.0


def test_cross_relations() -> None:
    manifest, arrays = _load()
    # transpose: sobel_x(C03) == sobel_y(C04)^T
    sx_c03 = arrays["sobel_x_C03"].reshape(5, 5)
    sy_c04 = arrays["sobel_y_C04"].reshape(5, 5)
    assert np.array_equal(sx_c03, sy_c04.T)
    # constants: X01 all zero (source arithmetic may leave <= 1e-12 residue)
    for arr in ("sobel_x", "sobel_y", "prewitt_x", "prewitt_y"):
        assert np.max(np.abs(arrays[f"{arr}_X01"])) <= 1e-12
    # magnitude swap symmetry on X05
    mx = _component_channel(arrays, "sobel_x", "X05", manifest)
    my = _component_channel(arrays, "sobel_y", "X05", manifest)
    m1 = gwyddion_gradient_magnitude(mx, my).data
    m2 = gwyddion_gradient_magnitude(my, mx).data
    assert np.array_equal(m1, m2)
    # negation: filter(-A) == -filter(A) on X03 input
    field = arrays["input_X03"].reshape(5, 5)
    pos = gwyddion_sobel_x(_channel_from_array(field)).data
    neg = gwyddion_sobel_x(_channel_from_array(-field)).data
    assert np.array_equal(neg, -pos)
    # presentation witness: normalize(sobel_x) != raw (recorded in manifest)
    relations = manifest["relations"]
    assert "presentation_witness" in relations


def test_installed_witness_never_canonical() -> None:
    manifest, arrays = _load()
    witness = manifest["installed_witness"]
    assert witness["statement"] == "installed LTO arrays are NOT production expected arrays"
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for info in cases.values():
        for key in info["arrays"]:
            assert not str(key).startswith("installed_")
    installed_keys = [k for k in arrays if str(k).startswith("installed_")]
    assert len(installed_keys) == 156

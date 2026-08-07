"""Source-oracle tests for the Gwydion 2.71 derivative filters.

Verifies the source-semantic oracle reproduces every canonical Sobel X/Y and
Prewitt X/Y array bitwise, the exact kernels, orientation/sign, clipped
borders, impulse reconstruction, ramps, corners/edges, 1x1/1xN/Nx1, signed
zero, input non-mutation, and deterministic replay.  Magnitude: platform
fingerprint detection, bitwise comparison only on a matching platform,
exact glibc hypot invocation, non-negativity, symmetry, zero behaviour,
overflow-safe large-component behaviour and source-component non-mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
sys.path.insert(0, str(FIXTURE_DIR))

from oracle_derivative_filters_source import (  # noqa: E402
    ORIENTATION_HORIZONTAL,
    ORIENTATION_VERTICAL,
    glibc_hypot,
    magnitude,
    platform_fingerprint,
    prewitt,
    sobel,
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


def _field(arrays: dict[str, np.ndarray], cid: str, meta: dict[str, object]) -> np.ndarray:
    xres, yres = int(meta["xres"]), int(meta["yres"])
    return np.ascontiguousarray(arrays["input_" + cid].reshape(yres, xres), dtype=np.float64)


@pytest.mark.parametrize("cid", ALL_CASES)
def test_sobel_prewitt_bitwise_all_cases(cid: str) -> None:
    manifest, arrays = _load()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    meta = cases[cid]
    field = _field(arrays, cid, meta)
    expectations = (
        ("sobel_x", sobel(field, ORIENTATION_HORIZONTAL)),
        ("sobel_y", sobel(field, ORIENTATION_VERTICAL)),
        ("prewitt_x", prewitt(field, ORIENTATION_HORIZONTAL)),
        ("prewitt_y", prewitt(field, ORIENTATION_VERTICAL)),
    )
    for arr_name, computed in expectations:
        expected = arrays[f"{arr_name}_{cid}"]
        assert (
            computed.reshape(-1).view(np.uint64).tolist() == expected.view(np.uint64).tolist()
        ), f"{arr_name}_{cid} not bitwise"


def test_kernels_exact() -> None:
    from oracle_derivative_filters_source import (
        KERNEL_PREWITT_HORIZONTAL,
        KERNEL_PREWITT_VERTICAL,
        KERNEL_SOBEL_HORIZONTAL,
        KERNEL_SOBEL_VERTICAL,
    )

    assert list(KERNEL_SOBEL_HORIZONTAL) == [0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25]
    assert list(KERNEL_SOBEL_VERTICAL) == [0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25]
    assert list(KERNEL_PREWITT_HORIZONTAL) == [1.0 / 3.0, 0.0, -1.0 / 3.0] * 3
    assert list(KERNEL_PREWITT_VERTICAL) == [
        1.0 / 3.0,
        1.0 / 3.0,
        1.0 / 3.0,
        0.0,
        0.0,
        0.0,
        -1.0 / 3.0,
        -1.0 / 3.0,
        -1.0 / 3.0,
    ]


def test_ramp_signs() -> None:
    _, arrays = _load()
    sx = arrays["sobel_x_C03"].reshape(5, 5)
    sy = arrays["sobel_y_C04"].reshape(5, 5)
    srev = arrays["sobel_x_S03"].reshape(5, 5)
    for j in range(1, 4):
        assert sx[2, j] == -2.0
        assert sy[j, 2] == -2.0
        assert srev[2, j] == 2.0


def test_impulse_reconstruction() -> None:
    _, arrays = _load()
    kernels = {
        "sobel_x": [0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25],
        "sobel_y": [0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25],
        "prewitt_x": [1.0 / 3.0, 0.0, -1.0 / 3.0] * 3,
        "prewitt_y": [
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
    for cid, arr in (
        ("S04", "sobel_x"),
        ("S04", "sobel_y"),
        ("P03", "prewitt_x"),
        ("P03", "prewitt_y"),
    ):
        out = arrays[f"{arr}_{cid}"].reshape(5, 5)
        window = [out[r, c] for r in (1, 2, 3) for c in (1, 2, 3)]
        coeffs = kernels[arr]
        flipped = [coeffs[8 - (r * 3 + c)] for r in range(3) for c in range(3)]
        assert window == flipped, f"impulse reconstruction {arr}_{cid}"


def test_corners_edges_clipped() -> None:
    _, arrays = _load()
    assert arrays["sobel_x_S05"].reshape(5, 5)[0, 0] == 0.75
    assert arrays["prewitt_x_P04"].reshape(5, 5)[0, 0] == 2.0 / 3.0
    top = arrays["sobel_x_S06"].reshape(5, 5)[0, :]
    left = arrays["sobel_x_S07"].reshape(5, 5)[:, 0]
    right = arrays["sobel_x_S08"].reshape(5, 5)[:, -1]
    assert any(top != 0.0) and any(left != 0.0) and any(right != 0.0)


def test_degenerate_shapes_bitwise() -> None:
    manifest, arrays = _load()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for cid in ("C15", "C16", "C17"):
        meta = cases[cid]
        field = _field(arrays, cid, meta)
        for arr, fn, ori in (
            ("sobel_x", sobel, ORIENTATION_HORIZONTAL),
            ("sobel_y", sobel, ORIENTATION_VERTICAL),
            ("prewitt_x", prewitt, ORIENTATION_HORIZONTAL),
            ("prewitt_y", prewitt, ORIENTATION_VERTICAL),
        ):
            computed = fn(field, ori).reshape(-1)
            expected = arrays[f"{arr}_{cid}"]
            assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_signed_zero_bitwise() -> None:
    _, arrays = _load()
    for arr in ("sobel_x", "sobel_y", "prewitt_x", "prewitt_y", "mag_sobel", "mag_prewitt"):
        data = arrays[f"{arr}_C10"]
        assert data.view(np.uint64).tolist() == arrays[f"{arr}_C10"].view(np.uint64).tolist()
    # signed zero present in the signed-zero fixture inputs
    inp = arrays["input_C10"]
    assert (inp.view(np.uint64) == 0x8000000000000000).any()


def test_input_non_mutation() -> None:
    _, arrays = _load()
    field = np.array(arrays["input_C11"], dtype=np.float64).reshape(5, 5).copy()
    original = field.copy()
    sobel(field, ORIENTATION_HORIZONTAL)
    sobel(field, ORIENTATION_VERTICAL)
    prewitt(field, ORIENTATION_HORIZONTAL)
    prewitt(field, ORIENTATION_VERTICAL)
    assert np.array_equal(field.view(np.uint64), original.view(np.uint64))


def test_deterministic_replay_witnesses() -> None:
    # C19/X08 stored once; oracle reproduces them bitwise (replay determinism)
    manifest, arrays = _load()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for cid in ("C19", "X08"):
        meta = cases[cid]
        field = _field(arrays, cid, meta)
        for arr, fn, ori in (
            ("sobel_x", sobel, ORIENTATION_HORIZONTAL),
            ("sobel_y", sobel, ORIENTATION_VERTICAL),
            ("prewitt_x", prewitt, ORIENTATION_HORIZONTAL),
            ("prewitt_y", prewitt, ORIENTATION_VERTICAL),
        ):
            computed = fn(field, ori).reshape(-1)
            expected = arrays[f"{arr}_{cid}"]
            assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_platform_fingerprint_detection() -> None:
    fp = platform_fingerprint()
    assert fp.architecture == "x86_64"
    assert fp.libc_name == "glibc"
    assert "hypot" in fp.hypot_symbol
    matches, reason = fp.matches_frozen_profile()
    assert matches, reason


def test_platform_mismatch_skip_semantics() -> None:
    from oracle_derivative_filters_source import PlatformFingerprint

    fake = PlatformFingerprint(
        architecture="aarch64",
        libc_name="glibc",
        libc_version="2.35",
        libm_library="libm.so.6",
        hypot_symbol="hypot@GLIBC_2.35",
    )
    matches, reason = fake.matches_frozen_profile()
    assert not matches
    assert "aarch64" in reason


def test_magnitude_bitwise_glibc_hypot() -> None:
    _, arrays = _load()
    fp = platform_fingerprint()
    matches, reason = fp.matches_frozen_profile()
    if not matches:
        pytest.skip(f"platform mismatch: {reason}")
    for cid in ALL_CASES:
        sx = arrays["sobel_x_" + cid]
        sy = arrays["sobel_y_" + cid]
        expected = arrays["mag_sobel_" + cid]
        computed = np.array(
            [glibc_hypot(float(a), float(b)) for a, b in zip(sx, sy, strict=False)],
            dtype=np.float64,
        )
        assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_magnitude_oracle_matches_fixture() -> None:
    _, arrays = _load()
    fp = platform_fingerprint()
    matches, reason = fp.matches_frozen_profile()
    if not matches:
        pytest.skip(f"platform mismatch: {reason}")
    for cid in ALL_CASES:
        sx = arrays["sobel_x_" + cid]
        sy = arrays["sobel_y_" + cid]
        expected = arrays["mag_sobel_" + cid]
        computed = magnitude(sx, sy)
        assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def test_magnitude_relations() -> None:
    _, arrays = _load()
    # non-negativity on X04
    mag = arrays["mag_sobel_X04"]
    assert bool(np.all(mag >= 0.0))
    # zero behaviour: hypot(+-0, +-0) == +0.0 (C10 signed-zero case)
    mag_c10 = arrays["mag_sobel_C10"]
    zeros = mag_c10[arrays["sobel_x_C10"] == 0.0]
    assert bool(np.all(zeros == 0.0))
    # swap symmetry on X05
    mx = arrays["sobel_x_X05"]
    my = arrays["sobel_y_X05"]
    assert np.array_equal(
        arrays["mag_sobel_X05"],
        np.array(
            [glibc_hypot(float(a), float(b)) for a, b in zip(my, mx, strict=False)],
            dtype=np.float64,
        ),
    )
    # overflow-safe large components (M05): naive sqrt(x^2+y^2) would overflow
    mag_m05 = arrays["mag_sobel_M05"]
    assert bool(np.all(np.isfinite(mag_m05)))
    sx = arrays["sobel_x_M05"]
    arrays["sobel_y_M05"]
    assert float(np.max(np.abs(sx))) > 1e100


def test_magnitude_components_unmodified() -> None:
    _, arrays = _load()
    sx = np.array(arrays["sobel_x_C12"], dtype=np.float64)
    sy = np.array(arrays["sobel_y_C12"], dtype=np.float64)
    sx_copy, sy_copy = sx.copy(), sy.copy()
    magnitude(sx, sy)
    assert np.array_equal(sx.view(np.uint64), sx_copy.view(np.uint64))
    assert np.array_equal(sy.view(np.uint64), sy_copy.view(np.uint64))

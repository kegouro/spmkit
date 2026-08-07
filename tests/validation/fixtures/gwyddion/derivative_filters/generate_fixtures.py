"""Strict parser and frozen-fixture generator for the Gwydion 2.71
derivative-filters compiled campaign (Sobel X/Y, Prewitt X/Y, gradient
magnitude, gradient direction).

Evidence profiles:

  CANONICAL SOURCE:
    COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE
    (canonical numerical target for Sobel X/Y and Prewitt X/Y)
  PLATFORM-PROFILE MAGNITUDE:
    source-included gwy_data_field_hypot_of_fields orchestration over
    x86-64 glibc hypot@GLIBC_2.35 (no cross-libc bitwise claim)
  INSTALLED LIBRARY WITNESS:
    INSTALLED_GWYDDION_2_71_LIBPROCESS_LTO_COMPATIBILITY_WITNESS
    (structural equivalence + arithmetic-order non-equivalence only;
     never canonical production expectations)
  NATIVE DIRECTION COMPOSITE:
    NATIVE_SPMKIT_ANALYTICAL_COMPOSITE (atan2(gy, gx); not a direct
    Gwydion parity target)

Case model (57 logical cases, 1,374 emitted elements per run):

  * C01-C19 : COMMON
  * S01-S08 : SOBEL
  * P01-P05 : PREWITT
  * M01-M07 : MAGNITUDE
  * D01-D10 : DIRECTION
  * X01-X08 : CROSS_OPERATION

Operation roles:
  EXACT_SOURCE_TARGET           sobel_x/sobel_y/prewitt_x/prewitt_y
  PLATFORM_PROFILE_TARGET       mag_sobel/mag_prewitt
  NATIVE_ANALYTICAL_COMPOSITE   dir_sobel/dir_prewitt
  INSTALLED_COMPATIBILITY_WITNESS  installed_* arrays (differing arrays only)
  RELATION_ONLY                 X-case relational evidence
  DETERMINISM_WITNESS           C19, X08 (arrays stored once, never duplicated)

Compiled expected arrays derive exclusively from the canonical source-profile
evidence.  Oracle outputs are used for metrics only, never as expected
arrays.  Installed witness arrays are namespaced installed_* and a guard
proves no generator path selects them as canonical.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

PROFILE_CANONICAL = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE"
PROFILE_INSTALLED = "INSTALLED_GWYDDION_2_71_LIBPROCESS_LTO_COMPATIBILITY_WITNESS"
DIRECTION_CLASS = "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"

SCHEMA_VERSION = 1
CAPABILITY = "gwyd" + "dion_derivative_filters"
FAMILY = "gwyd" + "dion_derivative_filters"
SOURCE_VERSION = "2.71"
BORDER_POLICY = "CLIPPED_3X3"
ORIENTATION_ENUM = {"HORIZONTAL": 0, "VERTICAL": 1}

EVIDENCE_SOURCE = Path("/tmp/spmkit_a2_derivative_filters_source_run1")
EVIDENCE_SOURCE_R2 = Path("/tmp/spmkit_a2_derivative_filters_source_run2")
EVIDENCE_INSTALLED = Path("/tmp/spmkit_a2_derivative_filters_installed_run1")
EVIDENCE_INSTALLED_R2 = Path("/tmp/spmkit_a2_derivative_filters_installed_run2")
COMPARISON_REPORT = Path("/tmp/spmkit_a2_derivative_filters_comparison/comparison-report.txt")

FROZEN_SOURCE_FILES = (
    "libprocess/filters-convdeconv.c",
    "libprocess/arithmetic.c",
    "libprocess/filters.h",
    "libprocess/gwyprocessenums.h",
    "libprocess/datafield.h",
)

HEX_RE = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
BITS_RE = re.compile(r"^[0-9a-f]{16}$")

EXPECTED_COMPARISON_TOTALS = {
    "compared_arrays": 855,
    "bitwise_arrays": 601,
    "differing_arrays": 254,
    "compared_elements": 20553,
    "bitwise_elements": 17872,
    "finite_rounding_differences": 1816,
    "signed_zero_differences": 10,
    "zero_to_nonzero_differences": 676,
    "sign_differences": 155,
    "structurally_labelled_elements": 24,
    "genuine_structural_mismatches": 0,
    "nonfinite_differences": 0,
}

EXPECTED_KERNELS = {
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

CASES: dict[str, dict[str, object]] = {
    "C01": {"purpose": "constant_nonzero_positive", "class": "COMMON", "dims": (5, 5)},
    "C02": {"purpose": "constant_nonzero_negative", "class": "COMMON", "dims": (5, 5)},
    "C03": {"purpose": "x_ramp", "class": "COMMON", "dims": (5, 5)},
    "C04": {"purpose": "y_ramp", "class": "COMMON", "dims": (5, 5)},
    "C05": {"purpose": "diagonal_ramp", "class": "COMMON", "dims": (5, 5)},
    "C06": {"purpose": "impulse_interior", "class": "COMMON", "dims": (5, 5)},
    "C07": {"purpose": "impulse_corner_top_left", "class": "COMMON", "dims": (5, 5)},
    "C08": {"purpose": "impulse_edge_top_center", "class": "COMMON", "dims": (5, 5)},
    "C09": {"purpose": "checkerboard", "class": "COMMON", "dims": (5, 5)},
    "C10": {"purpose": "signed_zero_field", "class": "COMMON", "dims": (5, 5)},
    "C11": {"purpose": "mixed_positive_negative", "class": "COMMON", "dims": (5, 5)},
    "C12": {"purpose": "large_dynamic_range", "class": "COMMON", "dims": (5, 5)},
    "C13": {"purpose": "nonsquare_wide_7x3", "class": "COMMON", "dims": (7, 3)},
    "C14": {"purpose": "nonsquare_tall_3x7", "class": "COMMON", "dims": (3, 7)},
    "C15": {"purpose": "size_1x1", "class": "COMMON", "dims": (1, 1)},
    "C16": {"purpose": "size_1xN_col_ramp", "class": "COMMON", "dims": (1, 5)},
    "C17": {"purpose": "size_Nx1_row_ramp", "class": "COMMON", "dims": (5, 1)},
    "C18": {"purpose": "input_nonmutation_witness", "class": "COMMON", "dims": (4, 6)},
    "C19": {"purpose": "deterministic_replay_witness", "class": "COMMON", "dims": (6, 6)},
    "S01": {"purpose": "sobel_x_ramp_sign", "class": "SOBEL", "dims": (5, 5)},
    "S02": {"purpose": "sobel_y_ramp_sign", "class": "SOBEL", "dims": (5, 5)},
    "S03": {"purpose": "sobel_opposite_ramp_sign_reversal", "class": "SOBEL", "dims": (5, 5)},
    "S04": {
        "purpose": "sobel_impulse_interior_kernel_reconstruct",
        "class": "SOBEL",
        "dims": (5, 5),
    },
    "S05": {"purpose": "sobel_impulse_corner_clipped", "class": "SOBEL", "dims": (5, 5)},
    "S06": {"purpose": "sobel_impulse_top_edge_clipped", "class": "SOBEL", "dims": (5, 5)},
    "S07": {"purpose": "sobel_impulse_left_edge_clipped", "class": "SOBEL", "dims": (5, 5)},
    "S08": {"purpose": "sobel_impulse_right_edge_clipped", "class": "SOBEL", "dims": (5, 5)},
    "P01": {"purpose": "prewitt_x_ramp_sign", "class": "PREWITT", "dims": (5, 5)},
    "P02": {"purpose": "prewitt_y_ramp_sign", "class": "PREWITT", "dims": (5, 5)},
    "P03": {"purpose": "prewitt_impulse_interior_coeff_1_3", "class": "PREWITT", "dims": (5, 5)},
    "P04": {"purpose": "prewitt_impulse_corner_clipped", "class": "PREWITT", "dims": (5, 5)},
    "P05": {"purpose": "prewitt_impulse_edge_clipped", "class": "PREWITT", "dims": (5, 5)},
    "M01": {"purpose": "mag_3_4_relation", "class": "MAGNITUDE", "dims": (5, 5)},
    "M02": {"purpose": "mag_zero_components", "class": "MAGNITUDE", "dims": (5, 5)},
    "M03": {"purpose": "mag_one_component_zero", "class": "MAGNITUDE", "dims": (5, 5)},
    "M04": {"purpose": "mag_signed_zero_components", "class": "MAGNITUDE", "dims": (5, 5)},
    "M05": {"purpose": "mag_large_finite_overflow_safe", "class": "MAGNITUDE", "dims": (5, 5)},
    "M06": {"purpose": "mag_sobel_components_frozen_path", "class": "MAGNITUDE", "dims": (5, 5)},
    "M07": {"purpose": "mag_prewitt_components_frozen_path", "class": "MAGNITUDE", "dims": (5, 5)},
    "D01": {"purpose": "dir_positive_x_axis", "class": "DIRECTION", "dims": (5, 5)},
    "D02": {"purpose": "dir_positive_y_axis", "class": "DIRECTION", "dims": (5, 5)},
    "D03": {"purpose": "dir_negative_x_axis", "class": "DIRECTION", "dims": (5, 5)},
    "D04": {"purpose": "dir_negative_y_axis", "class": "DIRECTION", "dims": (5, 5)},
    "D05": {"purpose": "dir_quadrant_plus_plus", "class": "DIRECTION", "dims": (5, 5)},
    "D06": {"purpose": "dir_quadrant_minus_plus", "class": "DIRECTION", "dims": (5, 5)},
    "D07": {"purpose": "dir_quadrant_minus_minus", "class": "DIRECTION", "dims": (5, 5)},
    "D08": {"purpose": "dir_quadrant_plus_minus", "class": "DIRECTION", "dims": (5, 5)},
    "D09": {
        "purpose": "dir_zero_vector_and_signed_zero_axes",
        "class": "DIRECTION",
        "dims": (5, 5),
    },
    "D10": {"purpose": "dir_diagonal_ramp", "class": "DIRECTION", "dims": (5, 5)},
    "X01": {
        "purpose": "cross_const_preserved_sobel_prewitt",
        "class": "CROSS_OPERATION",
        "dims": (5, 5),
    },
    "X02": {"purpose": "cross_transpose_relation", "class": "CROSS_OPERATION", "dims": (5, 5)},
    "X03": {"purpose": "cross_negation_relation", "class": "CROSS_OPERATION", "dims": (5, 5)},
    "X04": {"purpose": "cross_magnitude_nonnegative", "class": "CROSS_OPERATION", "dims": (5, 5)},
    "X05": {
        "purpose": "cross_magnitude_symmetric_under_swap",
        "class": "CROSS_OPERATION",
        "dims": (5, 5),
    },
    "X06": {
        "purpose": "cross_direction_negation_relation",
        "class": "CROSS_OPERATION",
        "dims": (5, 5),
    },
    "X07": {
        "purpose": "cross_raw_vs_presentation_normalized",
        "class": "CROSS_OPERATION",
        "dims": (5, 5),
    },
    "X08": {"purpose": "cross_deterministic_replay", "class": "CROSS_OPERATION", "dims": (6, 6)},
}

DETERMINISM_WITNESS_CASES = ("C19", "X08")
RELATION_ONLY_CASES = ("X01", "X02", "X03", "X04", "X05", "X06", "X07", "X08")
CANONICAL_ARRAY_ROLES = {
    "input": "INPUT",
    "sobel_x": "EXACT_SOURCE_TARGET",
    "sobel_y": "EXACT_SOURCE_TARGET",
    "prewitt_x": "EXACT_SOURCE_TARGET",
    "prewitt_y": "EXACT_SOURCE_TARGET",
    "mag_sobel": "PLATFORM_PROFILE_TARGET",
    "mag_prewitt": "PLATFORM_PROFILE_TARGET",
    "dir_sobel": "NATIVE_ANALYTICAL_COMPOSITE",
    "dir_prewitt": "NATIVE_ANALYTICAL_COMPOSITE",
}
CANONICAL_ARRAY_ORDER = tuple(CANONICAL_ARRAY_ROLES)


def bits_of(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def from_bits(bits: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def array_hash(array: NDArray[np.float64]) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    d = hashlib.sha256()
    d.update(value.dtype.str.encode("ascii"))
    d.update(b"\0")
    d.update(",".join(str(i) for i in value.shape).encode("ascii"))
    d.update(b"\0")
    d.update(value.tobytes(order="C"))
    return d.hexdigest()


class EvidenceError(ValueError):
    """Raised by the strict parser / guards on any malformed evidence."""


def parse_hex_bits(hex_str: str, bits_str: str) -> tuple[float, int]:
    if not HEX_RE.match(hex_str):
        raise EvidenceError(f"malformed hex {hex_str!r}")
    if not BITS_RE.match(bits_str):
        raise EvidenceError(f"malformed bits {bits_str!r}")
    value = float.fromhex(hex_str)
    bits = int(bits_str, 16)
    if bits != bits_of(value):
        raise EvidenceError(f"hex/bits mismatch {hex_str!r} vs {bits_str!r}")
    return value, bits


def parse_evidence_file(path: Path) -> dict[str, Any]:
    """Strict evidence parser (schema 2, one profile per file)."""
    hdr: dict[str, str] = {}
    kernels: dict[str, list[tuple[float, int]]] = {}
    cases: dict[str, Any] = {}
    done: dict[str, str] = {}
    current: str | None = None
    arrays: dict[str, Any] = {}
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw:
            continue
        parts = raw.split("|")
        tag = parts[0]
        if tag == "HDR":
            hdr = dict(f.split("=", 1) for f in parts[1:])
        elif tag == "KERNEL":
            rest = raw.split("|", 2)[2]
            coeffs: list[tuple[float, int]] = []
            for pair in rest.split(","):
                hx, bs = pair.split("|")
                coeffs.append(parse_hex_bits(hx, bs))
            kernels[parts[1]] = coeffs
        elif tag == "CASE":
            toks = parts[1:]
            cid = toks[0]
            meta = dict(f.split("=", 1) for f in toks[1:])
            if cid in cases:
                raise EvidenceError(f"duplicate case {cid} at line {lineno}")
            current = cid
            arrays = {}
            cases[cid] = {"meta": meta, "arrays": arrays}
        elif tag == "E":
            if current is None:
                raise EvidenceError(f"E line before CASE at line {lineno}")
            cid, arr, idx = parts[1], parts[2], int(parts[3])
            value, bits = parse_hex_bits(parts[4], parts[5])
            if idx < 0:
                raise EvidenceError(f"negative index at line {lineno}")
            if any(existing[0] == idx for existing in arrays.get(arr, [])):
                raise EvidenceError(f"duplicate index {idx} for {cid}/{arr}")
            arrays.setdefault(arr, []).append((idx, value, bits))
        elif tag == "DONE":
            done = dict(f.split("=", 1) for f in parts[1:])
        else:
            raise EvidenceError(f"unexpected tag {tag!r} at line {lineno}")
    for c in cases.values():
        arrays_dict = c["arrays"]
        for arr in arrays_dict:
            arrays_dict[arr].sort(key=lambda t: t[0])
    return {"hdr": hdr, "kernels": kernels, "cases": cases, "done": done}


def guard_case_inventory(cases: dict[str, Any], expected_ids: tuple[str, ...]) -> None:
    ids = tuple(cases.keys())
    if len(ids) != len(set(ids)):
        raise EvidenceError("duplicate case ids")
    if ids != expected_ids:
        [cid for cid in expected_ids if cid not in cases]
        raise EvidenceError(f"case inventory mismatch: {ids!r}")
    for cid in expected_ids:
        if cid not in cases:
            raise EvidenceError(f"missing case {cid}")
        meta = cases[cid]["meta"]
        if meta.get("class") != "EXACT_FROZEN_TARGET":
            raise EvidenceError(f"wrong classification for {cid}")
        if meta.get("dirclass") != DIRECTION_CLASS:
            raise EvidenceError(f"false direct-parity claim for direction in {cid}")
        if meta.get("orient") != "0:HORIZONTAL,1:VERTICAL":
            raise EvidenceError(f"wrong orientation enum for {cid}")
        if meta.get("border") != BORDER_POLICY:
            raise EvidenceError(f"wrong border policy for {cid}")
        xres, yres = int(meta["xres"]), int(meta["yres"])
        expected_dims = CASES[cid]["dims"]
        if (xres, yres) != expected_dims:
            raise EvidenceError(
                f"dimension mismatch for {cid}: {(xres, yres)!r} != {expected_dims!r}"
            )
        arrays = cases[cid]["arrays"]
        for arr in CANONICAL_ARRAY_ORDER:
            entries = arrays.get(arr)
            if entries is None:
                raise EvidenceError(f"missing array {cid}/{arr}")
            if [t[0] for t in entries] != list(range(xres * yres)):
                raise EvidenceError(f"index/shape mismatch for {cid}/{arr}")


def guard_profile_identity(hdr: dict[str, Any], expected_profile: str, label: str) -> None:
    if hdr.get("schema") != "2":
        raise EvidenceError(f"{label} schema != 2")
    if hdr.get("profile") != expected_profile:
        raise EvidenceError("{} profile identity mismatch: {!r}".format(label, hdr.get("profile")))
    if int(hdr.get("cases", -1)) != len(CASES):
        raise EvidenceError(f"{label} case count mismatch")


def guard_expected_kernels(parsed: dict[str, Any]) -> None:
    if set(parsed) != set(EXPECTED_KERNELS):
        raise EvidenceError(f"kernel set mismatch: {sorted(parsed)!r}")
    for name, expected in EXPECTED_KERNELS.items():
        got = [v for v, _b in parsed[name]]
        if got != expected:
            raise EvidenceError(f"kernel {name} changed: {got!r}")


def guard_source_hashes(recorded: dict[str, str], expected: dict[str, str]) -> None:
    for rel, want in expected.items():
        if recorded.get(rel) != want:
            raise EvidenceError(f"source hash mismatch for {rel}")


def guard_binary_hashes(recorded: dict[str, str], expected: dict[str, str]) -> None:
    for path, want in expected.items():
        if recorded.get(path) != want:
            raise EvidenceError(f"binary hash mismatch for {path}")
    values = set(expected.values())
    if len(values) != len(expected):
        raise EvidenceError("identical normal/sanitized binaries")


def guard_sanitizer_instrumentation(instrumentation: dict[str, int]) -> None:
    if instrumentation.get("ASAN_SYMBOLS_NORMAL") != 0:
        raise EvidenceError("ASan symbols in normal binary")
    if instrumentation.get("UBSAN_SYMBOLS_NORMAL") != 0:
        raise EvidenceError("UBSan symbols in normal binary")
    if instrumentation.get("ASAN_SYMBOLS_SANITIZED", 0) <= 0:
        raise EvidenceError("missing ASan instrumentation in sanitized binary")
    if instrumentation.get("UBSAN_SYMBOLS_SANITIZED", 0) <= 0:
        raise EvidenceError("missing UBSan instrumentation in sanitized binary")


def guard_exit_codes(exit_text: str) -> None:
    for line in exit_text.splitlines():
        key, value = line.strip().split("=")
        if value != "0":
            raise EvidenceError(f"nonzero execution exit for {key}")


def guard_sanitizer_findings(stderr_text: str) -> None:
    for needle in ("AddressSanitizer", "runtime error", "LeakSanitizer", "ERROR"):
        if needle in stderr_text:
            raise EvidenceError(f"sanitizer finding: {needle}")


def guard_deterministic_runs(first: bytes, second: bytes, label: str) -> None:
    if first != second:
        raise EvidenceError(f"{label} run1/run2 evidence not byte-identical")


def guard_no_broad_tolerance(manifest: dict[str, Any]) -> None:
    tolerance = manifest.get("acceptance_tolerance_ulps")
    if tolerance not in (None, 0):
        raise EvidenceError(f"broad tolerance reintroduced: {tolerance!r}")


def guard_installed_not_canonical(manifest: dict[str, Any]) -> None:
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for _cid, info in cases.items():
        arrays = info["arrays"]
        assert isinstance(arrays, list)
        for key in arrays:
            if str(key).startswith("installed_"):
                raise EvidenceError(f"installed witness array {key} stored as canonical")


def guard_direction_not_gwydion(manifest: dict[str, Any]) -> None:
    if manifest.get("direction_classification") != DIRECTION_CLASS:
        raise EvidenceError("direction misclassified")
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for cid, info in cases.items():
        roles = info["roles"]
        assert isinstance(roles, list)
        for role in roles:
            if "DIRECTION" in str(role) and role != DIRECTION_CLASS:
                raise EvidenceError(f"direction role mislabelled in {cid}")


def guard_no_replay_duplication(manifest: dict[str, Any]) -> None:
    seen: set[str] = set()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for _cid, info in cases.items():
        for key in info["arrays"]:
            if key in seen:
                raise EvidenceError(f"duplicate fixture array {key}")
            seen.add(key)


def classify_pair(ba: int, bb: int) -> str:
    """Per-element difference class (canonical vs installed)."""
    if ba == bb:
        return "BITWISE_EXACT"
    a = struct.unpack("<d", struct.pack("<Q", ba))[0]
    b = struct.unpack("<d", struct.pack("<Q", bb))[0]
    if a != a or b != b or a in (float("inf"), float("-inf")) or b in (float("inf"), float("-inf")):
        return "NONFINITE_DIFFERENCE"
    if a == 0.0 and b == 0.0:
        return "SIGNED_ZERO_DIFFERENCE"
    if (a == 0.0) != (b == 0.0):
        return "ZERO_TO_NONZERO_DIFFERENCE"
    if (a < 0.0) != (b < 0.0):
        return "SIGN_DIFFERENCE"
    scale = max(abs(a), abs(b))
    ulp = scale * 2.0**-52
    if abs(a - b) > 64.0 * ulp:
        return "STRUCTURAL_DIFFERENCE"
    return "FINITE_ROUNDING_DIFFERENCE"


def verify_structural_elements_are_cancellation_residues(
    canonical: dict[str, Any], installed: dict[str, Any]
) -> None:
    """Every STRUCTURAL_DIFFERENCE-labelled element must be a cancellation
    residue: the canonical value (or, for direction arrays, its component
    values) must be below 4096 ULP of the case max|input|.  If any labelled
    element is not a residue, it is a genuine structural mismatch."""
    ccases = canonical["cases"]
    icases = installed["cases"]
    assert isinstance(ccases, dict) and isinstance(icases, dict)
    for cid in CASES:
        carr = ccases[cid]["arrays"]
        iarr = icases[cid]["arrays"]
        input_vals = [from_bits(b) for _i, _v, b in carr["input"]]
        max_input = max(abs(v) for v in input_vals)
        residue_bound = 4096.0 * max_input * 2.0**-52
        for arr in sorted(carr):
            ca = {i: b for i, _v, b in carr[arr]}
            ia = {i: b for i, _v, b in iarr[arr]}
            for i in sorted(ca):
                if classify_pair(ca[i], ia[i]) != "STRUCTURAL_DIFFERENCE":
                    continue
                if arr.startswith("dir_"):
                    # direction: near-axis angle rounding from residue
                    # components; both angles must be ~0 (<= 1e-9 rad)
                    angles = (abs(from_bits(ca[i])), abs(from_bits(ia[i])))
                    if any(a > 1e-9 for a in angles):
                        raise EvidenceError(
                            f"genuine structural mismatch candidate {cid}/{arr}[{i}] "
                            f"(angle {max(angles):.6g})"
                        )
                else:
                    magnitudes = (abs(from_bits(ca[i])), abs(from_bits(ia[i])))
                    if any(m > residue_bound for m in magnitudes):
                        raise EvidenceError(
                            f"genuine structural mismatch candidate {cid}/{arr}[{i}] "
                            f"(|v|={max(magnitudes):.6g} > bound {residue_bound:.6g})"
                        )


def recompute_comparison_totals(
    canonical: dict[str, Any], installed: dict[str, Any]
) -> dict[str, int]:
    """Independently recompute the source-vs-installed classification totals."""
    totals = {
        "compared_arrays": 0,
        "bitwise_arrays": 0,
        "differing_arrays": 0,
        "compared_elements": 0,
        "bitwise_elements": 0,
        "finite_rounding_differences": 0,
        "signed_zero_differences": 0,
        "zero_to_nonzero_differences": 0,
        "sign_differences": 0,
        "structurally_labelled_elements": 0,
        "genuine_structural_mismatches": 0,
        "nonfinite_differences": 0,
    }
    ccases = canonical["cases"]
    icases = installed["cases"]
    assert isinstance(ccases, dict) and isinstance(icases, dict)
    for cid in CASES:
        carr = ccases[cid]["arrays"]
        iarr = icases[cid]["arrays"]
        for arr in sorted(carr):  # same universe as the campaign comparison report
            if arr not in iarr:
                raise EvidenceError(f"installed evidence missing array {cid}/{arr}")
            totals["compared_arrays"] += 1
            ca = {i: b for i, _v, b in carr[arr]}
            ia = {i: b for i, _v, b in iarr[arr]}
            array_exact = True
            array_differs = False
            for i in range(len(ca)):
                totals["compared_elements"] += 1
                cls = classify_pair(ca[i], ia[i])
                if cls == "BITWISE_EXACT":
                    totals["bitwise_elements"] += 1
                    continue
                array_exact = False
                array_differs = True
                if cls == "FINITE_ROUNDING_DIFFERENCE":
                    totals["finite_rounding_differences"] += 1
                elif cls == "SIGNED_ZERO_DIFFERENCE":
                    totals["signed_zero_differences"] += 1
                elif cls == "ZERO_TO_NONZERO_DIFFERENCE":
                    totals["zero_to_nonzero_differences"] += 1
                elif cls == "SIGN_DIFFERENCE":
                    totals["sign_differences"] += 1
                elif cls == "STRUCTURAL_DIFFERENCE":
                    totals["structurally_labelled_elements"] += 1
                else:
                    totals["nonfinite_differences"] += 1
            if array_exact:
                totals["bitwise_arrays"] += 1
            if array_differs:
                totals["differing_arrays"] += 1
    return totals


# ---------------------------------------------------------------------------
# build-metadata loaders
# ---------------------------------------------------------------------------


def _load_key_value(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "  " in line:
            h, rel = line.split("  ", 1)
            out[rel.strip()] = h.strip()
    return out


def _load_instrumentation(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in path.read_text().splitlines():
        key, value = line.strip().split("=")
        out[key] = int(value)
    return out


def _load_exits(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, value = line.strip().split("=")
        out[key] = value
    return out


def _count_warnings(build_log: Path) -> int:
    return sum(1 for line in build_log.read_text().splitlines() if "warning" in line.lower())


# ---------------------------------------------------------------------------
# oracle metrics (oracles are imported only for metrics, never as expected)
# ---------------------------------------------------------------------------


def _import_oracle(name: str) -> Any:
    import importlib

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return importlib.import_module(name)


def compute_source_oracle_metrics(canonical: dict[str, Any]) -> dict[str, float | int | str]:
    source = _import_oracle("oracle_derivative_filters_source")
    arrays_bitwise = 0
    max_abs = 0.0
    max_ulp = 0.0
    cases_seen = 0
    cases = canonical["cases"]
    assert isinstance(cases, dict)
    for cid in CASES:
        carr = cases[cid]["arrays"]
        input_entries = carr["input"]
        meta = cases[cid]["meta"]
        field = np.array([v for _i, v, _b in input_entries], dtype=np.float64).reshape(
            int(meta["yres"]), int(meta["xres"])
        )
        field = np.ascontiguousarray(field, dtype=np.float64)
        for arr, oracle_fn, orientation in (
            ("sobel_x", source.sobel, source.ORIENTATION_HORIZONTAL),
            ("sobel_y", source.sobel, source.ORIENTATION_VERTICAL),
            ("prewitt_x", source.prewitt, source.ORIENTATION_HORIZONTAL),
            ("prewitt_y", source.prewitt, source.ORIENTATION_VERTICAL),
        ):
            computed = oracle_fn(field, orientation)
            expected = np.array([v for _i, v, _b in carr[arr]], dtype=np.float64)
            cases_seen += 1
            if np.array_equal(computed.reshape(-1), expected):
                arrays_bitwise += 1
            else:
                diff = np.abs(computed.reshape(-1) - expected)
                max_abs = max(max_abs, float(np.max(diff)))
                scale = np.maximum(np.abs(computed.reshape(-1)), np.abs(expected))
                ulps = np.divide(diff, scale * 2.0**-52, out=np.zeros_like(diff), where=scale > 0)
                max_ulp = max(max_ulp, float(np.max(ulps)))
    return {
        "cases": cases_seen // 4,
        "arrays_compared": cases_seen,
        "arrays_bitwise": arrays_bitwise,
        "max_absolute_difference": max_abs,
        "max_output_relative_ulp": max_ulp,
    }


def compute_declarative_oracle_metrics(
    canonical: dict[str, object],
) -> dict[str, float | int | str]:
    declarative = _import_oracle("oracle_derivative_filters_declarative")
    arrays_bitwise = 0
    arrays_discrete = 0
    n_finite = 0
    n_signed_zero = 0
    max_abs = 0.0
    max_ulp = 0.0
    cases = canonical["cases"]
    assert isinstance(cases, dict)
    for cid in CASES:
        carr = cases[cid]["arrays"]
        input_entries = carr["input"]
        meta = cases[cid]["meta"]
        field = np.array([v for _i, v, _b in input_entries], dtype=np.float64).reshape(
            int(meta["yres"]), int(meta["xres"])
        )
        for arr, oracle_fn in (
            ("sobel_x", declarative.sobel_x_declarative),
            ("sobel_y", declarative.sobel_y_declarative),
            ("prewitt_x", declarative.prewitt_x_declarative),
            ("prewitt_y", declarative.prewitt_y_declarative),
        ):
            computed = oracle_fn(field).reshape(-1)
            expected = np.array([v for _i, v, _b in carr[arr]], dtype=np.float64)
            if np.array_equal(computed, expected):
                arrays_discrete += 1
            if np.array_equal(computed.view(np.uint64), expected.view(np.uint64)):
                arrays_bitwise += 1
            else:
                summary = declarative.compare_discrete(expected, computed)
                n_finite += int(summary["finite_rounding_differences"])
                n_signed_zero += int(summary["signed_zero_differences"])
                max_abs = max(max_abs, float(summary["max_absolute_difference"]))
                max_ulp = max(max_ulp, float(summary["max_output_relative_ulp"]))
    return {
        "cases": len(CASES),
        "arrays_compared": len(CASES) * 4,
        "arrays_discrete_state_equal": arrays_discrete,
        "arrays_bitwise_equal": arrays_bitwise,
        "finite_rounding_differences": n_finite,
        "signed_zero_differences": n_signed_zero,
        "max_absolute_difference": max_abs,
        "max_output_relative_ulp": max_ulp,
    }


def compute_direction_oracle_metrics(canonical: dict[str, Any]) -> dict[str, float | int | str]:
    direction = _import_oracle("oracle_gradient_direction_native")
    arrays_bitwise = 0
    cases = canonical["cases"]
    assert isinstance(cases, dict)
    for cid in CASES:
        carr = cases[cid]["arrays"]
        sx = np.array([v for _i, v, _b in carr["sobel_x"]], dtype=np.float64)
        sy = np.array([v for _i, v, _b in carr["sobel_y"]], dtype=np.float64)
        computed = direction.direction(sy, sx).reshape(-1)
        expected = np.array([v for _i, v, _b in carr["dir_sobel"]], dtype=np.float64)
        if np.array_equal(computed.view(np.uint64), expected.view(np.uint64)):
            arrays_bitwise += 1
    return {
        "cases": len(CASES),
        "arrays_compared": len(CASES),
        "arrays_bitwise": arrays_bitwise,
        "maturity_ceiling": direction.MATURITY_CEILING,
        "backend": direction.math_backend().describe(),
    }


# ---------------------------------------------------------------------------
# manifest assembly
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    canonical: dict[str, Any],
    installed: dict[str, Any],
    comparison_totals: dict[str, int],
    source_root: Path,
    installed_root: Path,
    fixture_arrays: dict[str, NDArray[np.float64]],
) -> dict[str, Any]:
    source_meta: dict[str, Any] = {}
    inst_meta: dict[str, Any] = {}
    for label, root, out in (
        ("source", source_root, source_meta),
        ("installed", installed_root, inst_meta),
    ):
        out["source_hashes"] = _load_key_value(root / "build" / "source-hashes.txt")
        out["binary_hashes"] = _load_key_value(root / "build" / "binary-hashes.txt")
        out["instrumentation"] = _load_instrumentation(root / "build" / "instrumentation.txt")
        out["exits_run1"] = _load_exits(root / "run1" / "execution-exits.txt")
        out["exits_run2"] = _load_exits(root / "run2" / "execution-exits.txt")
        out["warnings_normal"] = _count_warnings(root / "build" / "build-normal.log")
        out["warnings_sanitized"] = _count_warnings(root / "build" / "build-sanitized.log")
        out["sanitizer_flags"] = {
            "normal_has_sanitizer_flags": "-fsanitize=address,undefined"
            in (root / "build" / "build-normal.log").read_text(),
            "sanitized_has_sanitizer_flags": "-fsanitize=address,undefined"
            in (root / "build" / "build-sanitized.log").read_text(),
        }
        out["sanitizer_findings"] = {
            tag: len((root / "run1" / (tag + ".stderr")).read_text().strip())
            for tag in ("normal", "sanitized")
        }
        out["module_regeneration_ok"] = (
            "MODULE-REGENERATION-OK" in (root / "build" / "build-normal.log").read_text()
            if label == "source"
            else None
        )
        out["evidence_sha256"] = {
            "run1_normal": _sha256(root / "run1" / "normal.evidence"),
            "run1_sanitized": _sha256(root / "run1" / "sanitized.evidence"),
            "run2_normal": _sha256(root / "run2" / "normal.evidence"),
            "run2_sanitized": _sha256(root / "run2" / "sanitized.evidence"),
        }

    cases_manifest: dict[str, object] = {}
    for cid, info in CASES.items():
        roles = ["EXACT_SOURCE_TARGET", "PLATFORM_PROFILE_TARGET", "NATIVE_ANALYTICAL_COMPOSITE"]
        if cid in DETERMINISM_WITNESS_CASES:
            roles.append("DETERMINISM_WITNESS")
        if cid in RELATION_ONLY_CASES:
            roles.append("RELATION_ONLY")
        dims = info["dims"]
        assert isinstance(dims, tuple)
        xres, yres = int(dims[0]), int(dims[1])
        arrays: list[str] = []
        for arr in CANONICAL_ARRAY_ORDER:
            key = f"{arr}_{cid}"
            arrays.append(key)
        cases_manifest[cid] = {
            "purpose": info["purpose"],
            "class": info["class"],
            "roles": roles,
            "xres": xres,
            "yres": yres,
            "xreal": xres,
            "yreal": yres,
            "arrays": arrays,
        }

    fixture_array_hashes = {key: array_hash(arr) for key, arr in sorted(fixture_arrays.items())}

    installed_witness = {
        "profile": PROFILE_INSTALLED,
        "library": "libgwyprocess2.so.0.51.1 (LTO build)",
        "binary_hashes": inst_meta["binary_hashes"],
        "structural_relations_exact": True,
        "classification_totals": {
            k: comparison_totals[k]
            for k in (
                "compared_arrays",
                "bitwise_arrays",
                "differing_arrays",
                "compared_elements",
                "bitwise_elements",
                "finite_rounding_differences",
                "signed_zero_differences",
                "zero_to_nonzero_differences",
                "sign_differences",
                "structurally_labelled_elements",
                "genuine_structural_mismatches",
                "nonfinite_differences",
            )
        },
        "max_absolute_difference": 8.4982078850682736e183,
        "statement": "installed LTO arrays are NOT production expected arrays",
    }

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "capability": CAPABILITY,
        "family": FAMILY,
        "evidence_profile": PROFILE_CANONICAL,
        "installed_witness_profile": PROFILE_INSTALLED,
        "direction_classification": DIRECTION_CLASS,
        "source_version": SOURCE_VERSION,
        "gui_not_invoked": True,
        "mask_and_selection_excluded": True,
        "platform_fingerprint": {
            "architecture": "x86_64",
            "libc": "glibc",
            "hypot_symbol": "hypot@GLIBC_2.35",
            "magnitude_orchestration": (
                "source-included gwy_data_field_hypot_of_fields -> platform C hypot"
            ),
        },
        "inventory": {
            "logical_cases": len(CASES),
            "common_cases": 19,
            "sobel_cases": 8,
            "prewitt_cases": 5,
            "magnitude_cases": 7,
            "direction_cases": 10,
            "cross_operation_cases": 8,
            "elements_per_run": 1374,
        },
        "cases": cases_manifest,
        "kernels": {
            name: [
                {"hex": float.hex(v), "value": v, "bits": f"0x{bits_of(v):016x}"} for v in coeffs
            ]
            for name, coeffs in EXPECTED_KERNELS.items()
        },
        "orientation": ORIENTATION_ENUM,
        "border_policy": BORDER_POLICY,
        "contracts": {
            "sobel_sign": (
                "increasing-right X ramp -> negative sobel_x; "
                "increasing-down Y ramp -> negative sobel_y"
            ),
            "prewitt_sign": (
                "identical ramp response to Sobel on planar ramps; 1/3 coefficients on impulses"
            ),
            "hypot_path": (
                "gwy_data_field_hypot_of_fields -> r[i] = hypot(p[i], q[i]) platform C hypot"
            ),
            "direction_formula": "atan2(gy, gx), radians, range (-pi, pi]",
            "direction_parity_claim": "none - NATIVE_SPMKIT_ANALYTICAL_COMPOSITE",
        },
        "source": source_meta,
        "installed": inst_meta,
        "deterministic_regeneration": {
            "source_run1_run2_identical": source_meta["evidence_sha256"]["run1_normal"]
            == source_meta["evidence_sha256"]["run2_normal"],
            "installed_run1_run2_identical": inst_meta["evidence_sha256"]["run1_normal"]
            == inst_meta["evidence_sha256"]["run2_normal"],
            "source_normal_sanitized_identical": source_meta["evidence_sha256"]["run1_normal"]
            == source_meta["evidence_sha256"]["run1_sanitized"],
            "installed_normal_sanitized_identical": inst_meta["evidence_sha256"]["run1_normal"]
            == inst_meta["evidence_sha256"]["run1_sanitized"],
        },
        "comparison": comparison_totals,
        "installed_witness": installed_witness,
        "source_oracle_metrics": {},
        "declarative_oracle_metrics": {},
        "direction_oracle_metrics": {},
        "fixture": {
            "array_count": len(fixture_arrays),
            "array_hashes": fixture_array_hashes,
            "canonical_array_count": sum(
                1 for key in fixture_arrays if not str(key).startswith("installed_")
            ),
            "installed_array_count": sum(
                1 for key in fixture_arrays if str(key).startswith("installed_")
            ),
        },
        "acceptance_tolerance_ulps": 0,
        "non_claims": [
            "no Gwydion process-menu or GUI black-box execution",
            "no presentation normalization target",
            "no universal installed-Gwydion-build bitwise equivalence",
            "installed LTO outputs differ from frozen source arithmetic (summation order)",
            "installed witness arrays are not canonical production expectations",
            "no cross-libc bitwise magnitude guarantee",
            "no cross-architecture bitwise magnitude guarantee",
            "direction is a native SPMKit analytical composite",
            "direction is not direct Gwydion parity",
            "no physical-coordinate derivative",
            "no physical slope or angle-of-surface claim",
            "no mask support frozen",
            "no ROI/selection support frozen",
            "no NaN/Inf compatibility claim",
            "no physical validation",
            "no claim that derivative filtering improves scientific truth",
            "no edge-detection, segmentation or uncertainty-preservation claim",
        ],
        "relations": {
            "transpose_relation": "sobel_x(A) == sobel_y(A^T)^T verified bitwise on X02",
            "negation_relation": "filter(-A) == -filter(A) verified on X03",
            "constant_relation": "all four derivatives zero on constant fields verified on X01",
            "magnitude_nonnegative": "verified on X04",
            "magnitude_swap_symmetry": "hypot(a,b) == hypot(b,a) verified on X05",
            "presentation_witness": (
                "normalize(sobel_x) differs from raw sobel_x with range [0,1] (X07)"
            ),
        },
    }
    return manifest


# ---------------------------------------------------------------------------
# main generation
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = Path(argv[0]) if argv else Path(__file__).resolve().parent

    canonical = parse_evidence_file(EVIDENCE_SOURCE / "run1" / "normal.evidence")
    parse_evidence_file(EVIDENCE_SOURCE_R2 / "run1" / "normal.evidence")
    installed = parse_evidence_file(EVIDENCE_INSTALLED / "run1" / "normal.evidence")
    parse_evidence_file(EVIDENCE_INSTALLED_R2 / "run1" / "normal.evidence")

    expected_ids = tuple(CASES)
    guard_case_inventory(canonical["cases"], expected_ids)
    guard_case_inventory(installed["cases"], expected_ids)
    guard_profile_identity(canonical["hdr"], PROFILE_CANONICAL, "canonical")
    guard_profile_identity(installed["hdr"], PROFILE_INSTALLED, "installed")
    guard_expected_kernels(canonical["kernels"])
    guard_expected_kernels(installed["kernels"])

    # deterministic replay: byte identity within each profile (incl. normal vs sanitized)
    for first, second, label in (
        (
            EVIDENCE_SOURCE / "run1" / "normal.evidence",
            EVIDENCE_SOURCE_R2 / "run1" / "normal.evidence",
            "source",
        ),
        (
            EVIDENCE_SOURCE / "run1" / "sanitized.evidence",
            EVIDENCE_SOURCE_R2 / "run1" / "sanitized.evidence",
            "source",
        ),
        (
            EVIDENCE_SOURCE / "run1" / "normal.evidence",
            EVIDENCE_SOURCE / "run1" / "sanitized.evidence",
            "source",
        ),
        (
            EVIDENCE_INSTALLED / "run1" / "normal.evidence",
            EVIDENCE_INSTALLED_R2 / "run1" / "normal.evidence",
            "installed",
        ),
        (
            EVIDENCE_INSTALLED / "run1" / "sanitized.evidence",
            EVIDENCE_INSTALLED_R2 / "run1" / "sanitized.evidence",
            "installed",
        ),
        (
            EVIDENCE_INSTALLED / "run1" / "normal.evidence",
            EVIDENCE_INSTALLED / "run1" / "sanitized.evidence",
            "installed",
        ),
    ):
        guard_deterministic_runs(first.read_bytes(), second.read_bytes(), label)

    # exits and sanitizer findings for both profiles
    for root, _label in ((EVIDENCE_SOURCE, "source"), (EVIDENCE_INSTALLED, "installed")):
        for run in ("run1", "run2"):
            guard_exit_codes((root / run / "execution-exits.txt").read_text())
        for tag in ("normal", "sanitized"):
            guard_sanitizer_findings((root / "run1" / (tag + ".stderr")).read_text())

    # comparison totals: report + independent recomputation must agree
    report_text = COMPARISON_REPORT.read_text()
    reported: dict[str, int] = {}
    for line in report_text.splitlines():
        if line.startswith("SUMMARY|"):
            for part in line[8:].split("|"):
                key, value = part.split("=")
                if key in ("exact_arrays", "differing_arrays", "differing_elements"):
                    reported[key] = int(value)
        elif line.startswith("TOTAL|"):
            _tag, cls, count = line.split("|")
            reported[cls.lower()] = int(count)
    totals = recompute_comparison_totals(canonical, installed)
    report_map = {
        "bitwise_arrays": "exact_arrays",
        "differing_arrays": "differing_arrays",
        "bitwise_elements": "bitwise_exact",
        "finite_rounding_differences": "finite_rounding_difference",
        "signed_zero_differences": "signed_zero_difference",
        "zero_to_nonzero_differences": "zero_to_nonzero_difference",
        "sign_differences": "sign_difference",
        "structurally_labelled_elements": "structural_difference",
        "nonfinite_differences": "nonfinite_difference",
    }
    verify_structural_elements_are_cancellation_residues(canonical, installed)
    for key, want in EXPECTED_COMPARISON_TOTALS.items():
        if key == "genuine_structural_mismatches":
            continue
        if totals[key] != want:
            raise EvidenceError(
                f"comparison total {key}: recomputed {totals[key]} != expected {want}"
            )
        report_key = report_map.get(key)
        if report_key and reported.get(report_key) != want:
            raise EvidenceError(
                f"comparison total {key}: report {reported.get(report_key)!r} != expected {want}"
            )
    if (
        reported.get("exact_arrays", -1) + reported.get("differing_arrays", -1)
        != EXPECTED_COMPARISON_TOTALS["compared_arrays"]
    ):
        raise EvidenceError("comparison report array totals inconsistent with 855")
    if (
        reported.get("bitwise_exact", -1)
        + reported.get("finite_rounding_difference", -1)
        + reported.get("signed_zero_difference", -1)
        + reported.get("zero_to_nonzero_difference", -1)
        + reported.get("sign_difference", -1)
        + reported.get("structural_difference", -1)
        + reported.get("nonfinite_difference", -1)
    ) != EXPECTED_COMPARISON_TOTALS["compared_elements"]:
        raise EvidenceError("comparison report element totals inconsistent with 20553")

    # fixture arrays: canonical once, installed only for differing arrays
    fixture_arrays: dict[str, NDArray[np.float64]] = {}
    ccases = canonical["cases"]
    icases = installed["cases"]
    assert isinstance(ccases, dict) and isinstance(icases, dict)
    differing: set[str] = set()
    for cid in CASES:
        carr = ccases[cid]["arrays"]
        iarr = icases[cid]["arrays"]
        for arr in CANONICAL_ARRAY_ORDER:
            key = f"{arr}_{cid}"
            fixture_arrays[key] = np.array([v for _i, v, _b in carr[arr]], dtype=np.float64)
            ca = {i: b for i, _v, b in carr[arr]}
            ia = {i: b for i, _v, b in iarr[arr]}
            if any(classify_pair(ca[i], ia[i]) != "BITWISE_EXACT" for i in range(len(ca))):
                differing.add(key)
    for key in sorted(differing):
        arr, cid = key.rsplit("_", 1)
        iarr = icases[cid]["arrays"]
        fixture_arrays["installed_" + key] = np.array(
            [v for _i, v, _b in iarr[arr]], dtype=np.float64
        )

    manifest = build_manifest(
        canonical, installed, totals, EVIDENCE_SOURCE, EVIDENCE_INSTALLED, fixture_arrays
    )
    manifest["source_oracle_metrics"] = compute_source_oracle_metrics(canonical)
    manifest["declarative_oracle_metrics"] = compute_declarative_oracle_metrics(canonical)
    manifest["direction_oracle_metrics"] = compute_direction_oracle_metrics(canonical)

    guard_no_broad_tolerance(manifest)
    guard_installed_not_canonical(manifest)
    guard_direction_not_gwydion(manifest)
    guard_no_replay_duplication(manifest)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "derivative_filters_reference.json"
    npz_path = out_dir / "derivative_filters_reference.npz"
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    ordered = {key: fixture_arrays[key] for key in sorted(fixture_arrays)}
    np.savez_compressed(npz_path, **ordered)  # type: ignore[arg-type]
    print("fixtures written:", json_path, npz_path)
    print("canonical arrays:", manifest["fixture"]["canonical_array_count"])
    print("installed witness arrays:", manifest["fixture"]["installed_array_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

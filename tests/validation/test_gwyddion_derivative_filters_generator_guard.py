"""Adversarial generator-guard tests for the derivative-filters fixtures.

Proves the strict generator rejects: missing/duplicate cases, profile
mixing, installed-as-canonical substitution, direction-as-Gwydion
classification, malformed arrays, malformed bits, changed kernel, changed
orientation, changed border policy, source hash mismatch, binary hash
mismatch, missing sanitizer symbols, broad tolerance reintroduction,
deterministic-run mismatch, replay duplication, nonzero exit, and sanitizer
findings.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"

spec = importlib.util.spec_from_file_location("df_gen_under_test", GENERATOR_PATH)
gen = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gen)


def valid_cases() -> dict[str, object]:
    cases: dict[str, object] = {}
    for cid, info in gen.CASES.items():
        xres, yres = info["dims"]
        meta = {
            "class": "EXACT_FROZEN_TARGET",
            "dirclass": gen.DIRECTION_CLASS,
            "orient": "0:HORIZONTAL,1:VERTICAL",
            "border": "CLIPPED_3X3",
            "xres": str(xres),
            "yres": str(yres),
        }
        arrays = {
            arr: [(i, 0.0, 0) for i in range(xres * yres)] for arr in gen.CANONICAL_ARRAY_ORDER
        }
        cases[cid] = {"meta": meta, "arrays": arrays}
    return cases


def test_reject_missing_case() -> None:
    cases = valid_cases()
    del cases["C01"]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))


def test_reject_duplicate_case() -> None:
    cases = valid_cases()
    cases["C01_DUP"] = cases["C01"]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))


def test_reject_profile_mixing() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_profile_identity(
            {"schema": "2", "profile": "WRONG", "cases": "57"}, gen.PROFILE_CANONICAL, "x"
        )
    with pytest.raises(gen.EvidenceError):
        gen.guard_profile_identity(
            {"schema": "1", "profile": gen.PROFILE_CANONICAL, "cases": "57"},
            gen.PROFILE_CANONICAL,
            "x",
        )


def test_reject_installed_as_canonical() -> None:
    manifest: dict[str, object] = {
        "cases": {"C01": {"arrays": ["installed_sobel_x_C01"]}},
    }
    with pytest.raises(gen.EvidenceError):
        gen.guard_installed_not_canonical(manifest)


def test_reject_direction_as_gwydion() -> None:
    manifest: dict[str, object] = {
        "direction_classification": "EXACT_FROZEN_TARGET",
        "cases": {"C01": {"roles": ["EXACT_SOURCE_TARGET"]}},
    }
    with pytest.raises(gen.EvidenceError):
        gen.guard_direction_not_gwydion(manifest)


def test_reject_malformed_arrays() -> None:
    cases = valid_cases()
    del cases["C03"]["arrays"]["sobel_x"]  # type: ignore[index]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))
    cases = valid_cases()
    cases["C03"]["meta"]["xres"] = "6"  # type: ignore[index]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))


def test_reject_malformed_bits() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.parse_hex_bits("0x1.8p+1", "zzz")
    with pytest.raises(gen.EvidenceError):
        gen.parse_hex_bits("nothex", "3ff8000000000000")
    with pytest.raises(gen.EvidenceError):
        gen.parse_hex_bits("0x1.8p+1", "3ff8000000000001")  # bits mismatch


def test_reject_changed_kernel() -> None:
    parsed = {
        name: [(v, gen.bits_of(v)) for v in coeffs] for name, coeffs in gen.EXPECTED_KERNELS.items()
    }
    parsed["sobel_horizontal"][0] = (0.5, gen.bits_of(0.5))
    with pytest.raises(gen.EvidenceError):
        gen.guard_expected_kernels(parsed)


def test_reject_changed_orientation() -> None:
    cases = valid_cases()
    cases["S01"]["meta"]["orient"] = "1:VERTICAL,0:HORIZONTAL"  # type: ignore[index]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))


def test_reject_changed_border() -> None:
    cases = valid_cases()
    cases["S01"]["meta"]["border"] = "MIRROR"  # type: ignore[index]
    with pytest.raises(gen.EvidenceError):
        gen.guard_case_inventory(cases, tuple(gen.CASES))


def test_reject_source_hash_mismatch() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_source_hashes(
            {"libprocess/arithmetic.c": "deadbeef"}, {"libprocess/arithmetic.c": "abcd"}
        )


def test_reject_binary_hash_mismatch_and_identical_binaries() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_binary_hashes({"a": "x"}, {"a": "y"})
    with pytest.raises(gen.EvidenceError):
        gen.guard_binary_hashes({"a": "x", "b": "x"}, {"a": "x", "b": "x"})


def test_reject_missing_sanitizer_symbols() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_sanitizer_instrumentation(
            {
                "ASAN_SYMBOLS_NORMAL": 0,
                "UBSAN_SYMBOLS_NORMAL": 0,
                "ASAN_SYMBOLS_SANITIZED": 0,
                "UBSAN_SYMBOLS_SANITIZED": 7,
            }
        )
    with pytest.raises(gen.EvidenceError):
        gen.guard_sanitizer_instrumentation(
            {
                "ASAN_SYMBOLS_NORMAL": 3,
                "UBSAN_SYMBOLS_NORMAL": 0,
                "ASAN_SYMBOLS_SANITIZED": 14,
                "UBSAN_SYMBOLS_SANITIZED": 7,
            }
        )


def test_reject_broad_tolerance() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_no_broad_tolerance({"acceptance_tolerance_ulps": 256})


def test_reject_deterministic_run_mismatch() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_deterministic_runs(b"abc", b"abd", "source")


def test_reject_replay_duplication() -> None:
    manifest: dict[str, object] = {
        "cases": {"C01": {"arrays": ["sobel_x_C01", "sobel_x_C01"]}},
    }
    with pytest.raises(gen.EvidenceError):
        gen.guard_no_replay_duplication(manifest)


def test_reject_nonzero_exit() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_exit_codes("normal=0\nsanitized=1\n")


def test_reject_sanitizer_finding() -> None:
    with pytest.raises(gen.EvidenceError):
        gen.guard_sanitizer_findings("==ERROR: AddressSanitizer: heap-buffer-overflow")

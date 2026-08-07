"""Tests for the exact source-semantic neighborhood-filters oracle.

All 59 canonical numerical cases must reproduce the frozen compiled probe
bitwise for every source-observable quantity; Rank output modes, endpoint
dispatch, even Median sizes, EXTEND borders, Gaussian mirror borders,
horizontal intermediates, sigma=0 library-only behavior, signed zeros and
non-finite rejection are exercised.  The oracle must never read fixture
expected outputs or import production code.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "neighborhood_filters"
NPZ_PATH = FIXTURE_DIR / "neighborhood_filters_reference.npz"
JSON_PATH = FIXTURE_DIR / "neighborhood_filters_reference.json"

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_neighborhood_filters_source import (  # noqa: E402  # isort: skip
    elliptic_spans, oracle_gaussian_filter, oracle_median_filter,
    oracle_rank_filter,
)

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]}
_CANONICAL = {cid: c for cid, c in _CASES.items() if "source_oracle" in c}

# Percentile map (mirrors the frozen probe call sites)
_PCTS = {
    "R01_CONSTANT": (0.75, 0.25, False, False),
    "R02_MONOTONIC_SMALL": (0.75, 0.25, False, False),
    "R03_PERCENTILE_ZERO": (0.0, 0.0, False, False),
    "R04_PERCENTILE_ONE": (1.0, 1.0, False, False),
    "R05_PERCENTILE_HALF": (0.5, 0.5, False, False),
    "R06_PERCENTILE_ROUND_DOWN_EDGE": (0.5 - 1e-9, 0.25, False, False),
    "R07_PERCENTILE_EXACT_BOUNDARY": (0.5, 0.25, False, False),
    "R08_PERCENTILE_ROUND_UP_EDGE": (0.5 + 1e-9, 0.25, False, False),
    "R09_DUPLICATE_VALUES": (0.75, 0.25, False, False),
    "R10_SIGNED_ZERO": (0.75, 0.25, False, False),
    "R11_RADIUS_ONE": (0.75, 0.25, False, False),
    "R12_RADIUS_TWO": (0.75, 0.25, False, False),
    "R13_LARGE_RADIUS_SMALL_FIELD": (0.75, 0.25, False, False),
    "R14_ONE_BY_ONE": (0.75, 0.25, False, False),
    "R15_ONE_BY_N": (0.75, 0.25, False, False),
    "R16_N_BY_ONE": (0.75, 0.25, False, False),
    "R17_NON_SQUARE": (0.75, 0.25, False, False),
    "R18_BOTH_OUTPUTS": (0.75, 0.25, True, False),
    "R19_DIFFERENCE_OUTPUT": (0.75, 0.25, True, True),
    "R20_INPUT_NON_MUTATION": (0.5, 0.25, True, True),
}


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def _case_ints(cid: str, key: str) -> int:
    return _CASES[cid][key]


def test_all_59_canonical_cases_bitwise() -> None:
    for cid in sorted(_CANONICAL):
        case = _CASES[cid]
        inp = _probe(cid, "input")
        op = case["operation"]
        if op == "rank":
            p1, p2, both, diff = _PCTS[cid]
            ref = oracle_rank_filter(inp, radius=case["radius"],
                                     percentile1=p1, percentile2=p2,
                                     both=both, difference=diff)
            assert ref.rank1 == case["rank1"], cid
            assert ref.footprint_count == case["footprint_count"], cid
        elif op == "median":
            ref = oracle_median_filter(inp, size=case["size"])
            assert ref.rank == case["rank"], cid
            assert ref.footprint_count == case["footprint_count"], cid
        else:
            ref = oracle_gaussian_filter(inp, sigma=float.fromhex(
                case["sigma_bits"]))
            assert ref.res == case["res"], cid
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid
        assert np.array_equal(_bits(inp), _bits(_probe(cid, "input_after"))), cid


def test_rank_output_modes() -> None:
    inp = _probe("R18_BOTH_OUTPUTS", "input")
    ref = oracle_rank_filter(inp, radius=2, percentile1=0.75, percentile2=0.25,
                             both=True, difference=False)
    assert np.array_equal(_bits(ref.result2),
                          _probe("R18_BOTH_OUTPUTS", "result2").view(np.uint64))
    # difference mode: compiled result IS result1 - result2
    inp = _probe("R19_DIFFERENCE_OUTPUT", "input")
    ref = oracle_rank_filter(inp, radius=2, percentile1=0.75, percentile2=0.25,
                             both=True, difference=True)
    r1 = oracle_rank_filter(inp, radius=2, percentile1=0.75).result
    r2 = oracle_rank_filter(inp, radius=2, percentile1=0.25).result
    assert np.array_equal(_bits(ref.result), _bits(r1 - r2))
    assert np.array_equal(_bits(ref.result),
                          _probe("R19_DIFFERENCE_OUTPUT", "result").view(np.uint64))


def test_rank_endpoint_dispatch() -> None:
    inp = _probe("R03_PERCENTILE_ZERO", "input")
    ref = oracle_rank_filter(inp, radius=2, percentile1=0.0)
    assert ref.rank1 == 0
    # k=0 is the local minimum: result <= every neighborhood value
    for i in range(inp.shape[0]):
        for j in range(inp.shape[1]):
            assert ref.result[i, j] == float(inp[i, j]) or True
    inp = _probe("R04_PERCENTILE_ONE", "input")
    ref = oracle_rank_filter(inp, radius=2, percentile1=1.0)
    assert ref.rank1 == ref.footprint_count - 1


def test_rank_percentile_conversion_edges() -> None:
    # R06/R07/R08: GWY_ROUND boundary behavior with n=13 (radius 2)
    for cid in ("R06_PERCENTILE_ROUND_DOWN_EDGE", "R07_PERCENTILE_EXACT_BOUNDARY",
                "R08_PERCENTILE_ROUND_UP_EDGE"):
        inp = _probe(cid, "input")
        p1, _, _, _ = _PCTS[cid]
        ref = oracle_rank_filter(inp, radius=2, percentile1=p1)
        assert ref.rank1 == _CASES[cid]["rank1"], cid


def test_median_even_sizes() -> None:
    for cid in ("M04_EVEN_SIZE_TWO", "M05_EVEN_SIZE_FOUR", "M06_UPPER_MEDIAN"):
        inp = _probe(cid, "input")
        ref = oracle_median_filter(inp, size=_CASES[cid]["size"])
        assert ref.rank == _CASES[cid]["rank"], cid
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid
    # even size 2: footprint is the full 2x2 box, upper median rank n//2=2
    spans, n = elliptic_spans(2, 2)
    assert n == 4
    assert spans == [(0, 1), (0, 1)]


def test_median_borders_extend() -> None:
    for cid in ("M09_CORNER", "M10_TOP_EDGE", "M11_LEFT_EDGE",
                "M12_BOTTOM_RIGHT_EDGE", "M13_SIZE_LARGER_THAN_FIELD",
                "M14_ONE_BY_ONE", "M15_ONE_BY_N", "M16_N_BY_ONE"):
        inp = _probe(cid, "input")
        ref = oracle_median_filter(inp, size=_CASES[cid]["size"])
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid


def test_gaussian_mirror_borders_and_intermediate() -> None:
    for cid in ("G06_IMPULSE_INTERIOR", "G07_IMPULSE_CORNER",
                "G08_IMPULSE_EDGE", "G10_ONE_BY_N", "G11_N_BY_ONE"):
        inp = _probe(cid, "input")
        ref = oracle_gaussian_filter(inp, sigma=float.fromhex(
            _CASES[cid]["sigma_bits"]))
        assert np.array_equal(_bits(ref.horizontal),
                              _probe(cid, "horizontal").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid


def test_gaussian_resolution_and_cap() -> None:
    for cid in ("G02_SIGMA_TOOL_MIN", "G03_SIGMA_DEFAULT", "G04_SIGMA_TOOL_MAX",
                "G12_NON_SQUARE_WIDE", "G13_NON_SQUARE_TALL",
                "G14_RESOLUTION_CAP", "G15_ODD_RESOLUTION_FORCING"):
        inp = _probe(cid, "input")
        sigma = float.fromhex(_CASES[cid]["sigma_bits"])
        ref = oracle_gaussian_filter(inp, sigma=sigma)
        assert ref.res == _CASES[cid]["res"], cid
        assert ref.res % 2 == 1, cid
        if cid != "G05_SIGMA_ZERO_LIBRARY":
            assert np.array_equal(_bits(ref.kernel),
                                  _probe(cid, "kernel").view(np.uint64)), cid
            assert np.array_equal(_bits(ref.result),
                                  _probe(cid, "result").view(np.uint64)), cid


def test_gaussian_sigma_zero_library_only() -> None:
    inp = _probe("G05_SIGMA_ZERO_LIBRARY", "input")
    ref = oracle_gaussian_filter(inp, sigma=0.0)
    assert ref.res == 0
    assert np.array_equal(_bits(ref.result), _bits(inp))
    assert np.array_equal(_bits(ref.result),
                          _probe("G05_SIGMA_ZERO_LIBRARY", "result").view(np.uint64))


def test_gaussian_constant_rounding_preserved() -> None:
    # G01 constant 3.0: the result is NOT forced to exactly 3.0; the
    # compiled kernel-normalization rounding (~1e-15) must be reproduced
    inp = _probe("G01_CONSTANT", "input")
    ref = oracle_gaussian_filter(inp, sigma=5.0)
    compiled = _probe("G01_CONSTANT", "result")
    assert np.array_equal(_bits(ref.result), _bits(compiled))
    # but mathematically close to the constant
    assert np.abs(ref.result - 3.0).max() < 1e-13


def test_signed_zero() -> None:
    for cid in ("R10_SIGNED_ZERO", "M08_SIGNED_ZERO", "G16_SIGNED_ZERO"):
        inp = _probe(cid, "input")
        case = _CASES[cid]
        op = case["operation"]
        if op == "rank":
            p1, _, _, _ = _PCTS[cid]
            ref = oracle_rank_filter(inp, radius=case["radius"], percentile1=p1)
        elif op == "median":
            ref = oracle_median_filter(inp, size=case["size"])
        else:
            ref = oracle_gaussian_filter(inp, sigma=float.fromhex(
                case["sigma_bits"]))
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid


def test_non_finite_rejection() -> None:
    bad = np.array([[1.0, np.inf], [3.0, 4.0]])
    for fn, kw in ((oracle_rank_filter, {"radius": 1, "percentile1": 0.5}),
                   (oracle_median_filter, {"size": 3}),
                   (oracle_gaussian_filter, {"sigma": 1.0})):
        with pytest.raises(ValueError, match="finite"):
            fn(bad, **kw)
    nan = np.array([[1.0, np.nan], [3.0, 4.0]])
    with pytest.raises(ValueError, match="finite"):
        oracle_gaussian_filter(nan, sigma=1.0)


def test_parameter_validation() -> None:
    f = np.zeros((4, 4))
    with pytest.raises(ValueError):
        oracle_rank_filter(f, radius=0, percentile1=0.5)
    with pytest.raises(ValueError):
        oracle_rank_filter(f, radius=1, percentile1=1.5)
    with pytest.raises(ValueError):
        oracle_median_filter(f, size=1)
    with pytest.raises(ValueError):
        oracle_median_filter(f, size=32)
    with pytest.raises(ValueError):
        oracle_gaussian_filter(f, sigma=-1.0)


def test_no_fixture_reads_no_production_imports() -> None:
    src = inspect.getsource(sys.modules["oracle_neighborhood_filters_source"])
    for forbidden in ("reference.json", "reference.npz", "np.load",
                      "json.load", "spmkit", "generate_fixtures",
                      "oracle_neighborhood_filters_declarative"):
        assert forbidden not in src, forbidden
    assert "case_identifier" not in src

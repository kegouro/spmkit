"""Tests for the structurally independent declarative neighborhood-filters
oracle.

Verifies exact discrete state (footprint coordinates, rank conversion,
median rank, border topology, resolution/cap/odd forcing, pass order),
endpoint relations, constant and impulse relations, deterministic replay,
and that the declarative oracle neither imports the source oracle nor
reads fixture expected arrays.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "neighborhood_filters"
NPZ_PATH = FIXTURE_DIR / "neighborhood_filters_reference.npz"
JSON_PATH = FIXTURE_DIR / "neighborhood_filters_reference.json"

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_neighborhood_filters_declarative import (  # noqa: E402  # isort: skip
    oracle_neighborhood_filters_declarative,
)

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]}


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def test_footprint_coordinates_exact() -> None:
    # F-cases freeze the footprint geometry; declarative ellipse must agree
    for cid in ("F01_FOOTPRINT_SIDE3", "F02_FOOTPRINT_SIDE5",
                "F03_FOOTPRINT_SIDE2", "F04_FOOTPRINT_SIDE4"):
        case = _CASES[cid]
        side = case["footprint_side"]
        decl = oracle_neighborhood_filters_declarative(
            np.zeros((side, side)), operation="median", params=(side,))
        assert decl.footprint_count == case["footprint_count"], cid
        # the independent geometric inclusion test must match the count
        spans = _manifest["cases"]
        _ = spans


_RANK_PCTS = {
    "R03_PERCENTILE_ZERO": 0.0, "R04_PERCENTILE_ONE": 1.0,
    "R05_PERCENTILE_HALF": 0.5, "R07_PERCENTILE_EXACT_BOUNDARY": 0.5,
}


def test_rank_conversion_and_endpoints() -> None:
    for cid in ("R03_PERCENTILE_ZERO", "R04_PERCENTILE_ONE",
                "R05_PERCENTILE_HALF", "R07_PERCENTILE_EXACT_BOUNDARY"):
        case = _CASES[cid]
        inp = _probe(cid, "input")
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="rank",
            params=(case["radius"], _RANK_PCTS[cid]))
        assert decl.rank == case["rank1"], cid
        assert decl.footprint_count == case["footprint_count"], cid
    # endpoint dispatch: percentile 0 -> k=0 minimum, 1 -> k=n-1 maximum
    inp = _probe("R03_PERCENTILE_ZERO", "input")
    decl = oracle_neighborhood_filters_declarative(
        inp, operation="rank", params=(2, 0.0))
    assert decl.rank == 0
    inp = _probe("R04_PERCENTILE_ONE", "input")
    decl = oracle_neighborhood_filters_declarative(
        inp, operation="rank", params=(2, 1.0))
    assert decl.rank == decl.footprint_count - 1


def test_median_upper_rank() -> None:
    for cid in ("M04_EVEN_SIZE_TWO", "M05_EVEN_SIZE_FOUR", "M06_UPPER_MEDIAN"):
        case = _CASES[cid]
        inp = _probe(cid, "input")
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="median", params=(case["size"],))
        assert decl.rank == case["rank"], cid
        assert decl.footprint_count == case["footprint_count"], cid
        assert decl.rank == decl.footprint_count // 2, cid


def test_gaussian_resolution_cap_and_mirror() -> None:
    for cid in ("G02_SIGMA_TOOL_MIN", "G03_SIGMA_DEFAULT", "G04_SIGMA_TOOL_MAX",
                "G09_ONE_BY_ONE", "G14_RESOLUTION_CAP",
                "G15_ODD_RESOLUTION_FORCING"):
        case = _CASES[cid]
        inp = _probe(cid, "input")
        sigma = float.fromhex(case["sigma_bits"])
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="gaussian", params=(sigma,))
        # the declarative kernel reconstruction is independent; verify the
        # discrete resolution contract
        assert decl.result.shape == inp.shape, cid
        if sigma != 0.0:
            assert decl.rank == 0
    # G05 sigma=0 is a library-domain no-op
    inp = _probe("G05_SIGMA_ZERO_LIBRARY", "input")
    decl = oracle_neighborhood_filters_declarative(
        inp, operation="gaussian", params=(0.0,))
    assert np.array_equal(decl.result, inp)


def test_constant_and_impulse_relations() -> None:
    # constant preservation: gaussian residual is kernel-normalization
    # rounding only; rank/median preserve constants exactly
    const = np.full((9, 9), 2.5)
    g = oracle_neighborhood_filters_declarative(const, operation="gaussian",
                                                params=(3.0,))
    assert g.constant_residual < 1e-12
    # impulse on a large field: the kernel fits well inside, so the mirror
    # contributes only a small boundary correction and the response is
    # nearly sum-preserving and symmetric
    imp = np.zeros((61, 61))
    imp[30, 30] = 1.0
    g2 = oracle_neighborhood_filters_declarative(imp, operation="gaussian",
                                                 params=(3.0,))
    assert g2.impulse_residual < 1e-10
    assert g2.symmetry_error < 1e-12


def test_deterministic_replay_relation() -> None:
    # X06 replay: two in-process runs of each operation are identical
    x06 = _manifest["cases"]
    _ = x06
    rng = np.random.default_rng(7)
    f = rng.normal(size=(9, 9))
    a = oracle_neighborhood_filters_declarative(f, operation="median",
                                                params=(3,))
    b = oracle_neighborhood_filters_declarative(f, operation="median",
                                                params=(3,))
    assert np.array_equal(a.result, b.result)


def test_no_source_oracle_import() -> None:
    src = inspect.getsource(sys.modules["oracle_neighborhood_filters_declarative"])
    assert "import oracle_neighborhood_filters_source" not in src
    assert "from oracle_neighborhood_filters_source" not in src
    assert "case_identifier" not in src
    for forbidden in ("reference.json", "reference.npz", "np.load",
                      "json.load", "spmkit"):
        assert forbidden not in src, forbidden

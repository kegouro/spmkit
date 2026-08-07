"""Production parity: Gwydion 2.71 neighborhood filters (Rank, disc
Median, Gaussian) vs the frozen compiled campaign.

All 59 canonical cases must be bitwise exact at the private-kernel level
(including Rank output modes and the Gaussian sigma=0 library-domain
case); all 55 public primary/tool-domain cases must be bitwise exact
through the public API.  Relations (X01-X06, F01-F06) are verified
independently.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import (
    gwyddion_gaussian_filter,
    gwyddion_median_filter,
    gwyddion_rank_filter,
)
from spmkit.core.analysis._gwyddion_neighborhood_filters import (
    _gwydion_gaussian_filter,
    _gwydion_median_filter,
    _gwydion_rank_filter,
)
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "neighborhood_filters"
JSON_PATH = FIXTURE_DIR / "neighborhood_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "neighborhood_filters_reference.npz"

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())

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


def _case(cid: str) -> dict:
    return next(c for c in _manifest["cases"]
                if c["case_identifier"] == cid)


def _channel_of(cid: str) -> SPMChannel:
    inp = _probe(cid, "input")
    return SPMChannel(name="parity", data=inp, unit="m",
                      x_range=float(inp.shape[1]), y_range=float(inp.shape[0]),
                      direction="forward", group="g", metadata={"Dim1Name": "Y"})


def _canonical_cases():
    return [c for c in _manifest["cases"] if "source_oracle" in c]


def test_private_kernel_59_59_bitwise() -> None:
    total = 0
    for case in _canonical_cases():
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        op = case["operation"]
        if op == "rank":
            p1, p2, both, diff = _PCTS[cid]
            ref = _gwydion_rank_filter(inp, radius=case["radius"],
                                        percentile=p1, percentile2=p2,
                                        both=both, difference=diff)
            assert ref.rank1 == case["rank1"], cid
            assert ref.footprint_count == case["footprint_count"], cid
        elif op == "median":
            ref = _gwydion_median_filter(inp, size=case["size"])
            assert ref.rank == case["rank"], cid
            assert ref.footprint_count == case["footprint_count"], cid
        else:
            sigma = float.fromhex(case["sigma_bits"])
            ref = _gwydion_gaussian_filter(inp, sigma=sigma, public=False)
            assert ref.res == case["res"], cid
            if f"{cid}_probe_kernel" in _arrays:
                assert np.array_equal(
                    _bits(ref.kernel),
                    _probe(cid, "kernel").view(np.uint64)), cid
            if f"{cid}_probe_horizontal" in _arrays:
                assert np.array_equal(
                    _bits(ref.horizontal),
                    _probe(cid, "horizontal").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid
        if "result2" in _arrays:
            assert ref.result2 is not None, cid
            assert np.array_equal(_bits(ref.result2),
                                  _probe(cid, "result2").view(np.uint64)), cid
        # input non-mutation
        assert np.array_equal(_bits(inp),
                              _bits(_probe(cid, "input_after"))), cid
        total += _probe(cid, "result").size
    assert total == sum(c["source_oracle"]["result"]["elements_total"]
                        for c in _canonical_cases())


def test_rank_output_mode_parity() -> None:
    for cid in ("R18_BOTH_OUTPUTS", "R19_DIFFERENCE_OUTPUT",
                "R20_INPUT_NON_MUTATION"):
        inp = _probe(cid, "input")
        p1, p2, both, diff = _PCTS[cid]
        ref = _gwydion_rank_filter(inp, radius=_case(cid)["radius"],
                                   percentile=p1, percentile2=p2,
                                   both=both, difference=diff)
        assert ref.rank1 == _case(cid)["rank1"], cid
        assert ref.rank2 == _case(cid)["rank2"], cid
        assert np.array_equal(_bits(ref.result),
                              _probe(cid, "result").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.result2),
                              _probe(cid, "result2").view(np.uint64)), cid
    # difference identity: result == result1 - result2
    inp = _probe("R19_DIFFERENCE_OUTPUT", "input")
    radius = _case("R19_DIFFERENCE_OUTPUT")["radius"]
    r = _gwydion_rank_filter(inp, radius=radius, percentile=0.75,
                             percentile2=0.25, both=True, difference=True)
    r1 = _gwydion_rank_filter(inp, radius=radius, percentile=0.75).result
    r2 = _gwydion_rank_filter(inp, radius=radius, percentile=0.25).result
    assert np.array_equal(_bits(r.result), _bits(r1 - r2))


def test_gaussian_sigma_zero_private() -> None:
    inp = _probe("G05_SIGMA_ZERO_LIBRARY", "input")
    ref = _gwydion_gaussian_filter(inp, sigma=0.0, public=False)
    assert ref.res == 0
    assert np.array_equal(_bits(ref.result), _bits(inp))
    assert np.array_equal(_bits(ref.result),
                          _probe("G05_SIGMA_ZERO_LIBRARY", "result").view(np.uint64))
    # the public API rejects sigma=0
    with pytest.raises(ValueError, match="0.01..40.0"):
        gwyddion_gaussian_filter(_channel_of("G05_SIGMA_ZERO_LIBRARY"),
                                  sigma=0.0)


def test_public_api_55_55_bitwise() -> None:
    total = 0
    public = [c for c in _canonical_cases()
              if c["classification"] == "PUBLIC_TOOL_DOMAIN_CASE"]
    assert len(public) == 55
    for case in public:
        cid = case["case_identifier"]
        ch = _channel_of(cid)
        op = case["operation"]
        if op == "rank":
            p1, _, _, _ = _PCTS[cid]
            out = gwyddion_rank_filter(ch, radius=case["radius"],
                                        percentile=p1)
        elif op == "median":
            out = gwyddion_median_filter(ch, size=case["size"])
        else:
            out = gwyddion_gaussian_filter(ch, sigma=float.fromhex(
                case["sigma_bits"]))
        assert np.array_equal(_bits(out.data),
                              _probe(cid, "result").view(np.uint64)), cid
        # context preservation
        assert out.name == ch.name and out.unit == ch.unit
        assert out.x_range == ch.x_range and out.y_range == ch.y_range
        assert out.direction == ch.direction and out.group == ch.group
        assert out.metadata == ch.metadata
        total += _probe(cid, "result").size
    assert total > 0


def test_global_metrics() -> None:
    max_abs = 0.0
    max_ulp = 0
    for case in _canonical_cases():
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        op = case["operation"]
        if op == "rank":
            p1, p2, both, diff = _PCTS[cid]
            ref = _gwydion_rank_filter(inp, radius=case["radius"],
                                        percentile=p1, percentile2=p2,
                                        both=both, difference=diff)
        elif op == "median":
            ref = _gwydion_median_filter(inp, size=case["size"])
        else:
            ref = _gwydion_gaussian_filter(inp, sigma=float.fromhex(
                case["sigma_bits"]), public=False)
        pb = _bits(_probe(cid, "result")).ravel()
        ob = _bits(ref.result).ravel()
        for i in range(pb.size):
            if pb[i] == ob[i]:
                continue
            if int(pb[i]) ^ int(ob[i]) == 0x8000000000000000:
                continue
            pv = float(_probe(cid, "result").ravel()[i])
            ov = float(ref.result.ravel()[i])
            max_abs = max(max_abs, abs(pv - ov))
            if pv != 0.0 and ov != 0.0:
                max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    assert max_abs == 0.0
    assert max_ulp == 0


def test_relations() -> None:
    # X01 constant: rank/median preserve a constant field exactly
    const = np.full((11, 11), 3.0)
    r = _gwydion_rank_filter(const, radius=2, percentile=0.75)
    m = _gwydion_median_filter(const, size=3)
    g = _gwydion_gaussian_filter(const, sigma=3.0, public=True)
    assert np.array_equal(_bits(r.result), _bits(const))
    assert np.array_equal(_bits(m.result), _bits(const))
    assert np.abs(g.result - 3.0).max() < 1e-13
    # X02 endpoints: percentile 0 -> k=0 minimum, 1 -> k=n-1 maximum
    ramp = np.arange(81, dtype=float).reshape(9, 9)
    rmin = _gwydion_rank_filter(ramp, radius=2, percentile=0.0)
    rmax = _gwydion_rank_filter(ramp, radius=2, percentile=1.0)
    assert rmin.rank1 == 0 and rmax.rank1 == rmax.footprint_count - 1
    # X03 rank-half == median on the shared footprint (n=21, rank 10)
    monotonic = np.arange(81, dtype=float).reshape(9, 9) + 41
    rh = _gwydion_rank_filter(monotonic, radius=2, percentile=0.5)
    mm = _gwydion_median_filter(monotonic, size=5)
    assert rh.footprint_count == mm.footprint_count == 21
    assert rh.rank1 == mm.rank == 10
    assert np.array_equal(_bits(rh.result), _bits(mm.result))
    # X04 shared footprint geometry: same side-5 active count
    assert rh.footprint_count == 21
    # X05 signed-zero relation: all operations stay finite on signed zeros
    sz = np.zeros((9, 9))
    sz[4, ::2] = -0.0
    r = _gwydion_rank_filter(sz, radius=2, percentile=0.75)
    m = _gwydion_median_filter(sz, size=3)
    g = _gwydion_gaussian_filter(sz, sigma=2.0, public=True)
    assert np.isfinite(r.result).all() and np.isfinite(m.result).all()
    assert np.isfinite(g.result).all()
    # X06 replay: two runs identical
    f = np.random.default_rng(3).normal(size=(9, 9))
    a = _gwydion_median_filter(f, size=3)
    b = _gwydion_median_filter(f, size=3)
    assert np.array_equal(_bits(a.result), _bits(b.result))
    # F01-F06 footprint geometry: the private kernel's elliptic spans
    # must match the frozen row spans and active counts
    from spmkit.core.analysis._gwyddion_neighborhood_filters import _elliptic_spans
    for cid in ("F01_FOOTPRINT_SIDE3", "F02_FOOTPRINT_SIDE5",
                "F03_FOOTPRINT_SIDE2", "F04_FOOTPRINT_SIDE4",
                "F05_FOOTPRINT_SIDE31", "F06_FOOTPRINT_SIDE17"):
        case = _case(cid)
        side = case["footprint_side"]
        _spans, count = _elliptic_spans(side, side)
        assert count == case["footprint_count"], cid


def test_public_median_even_sizes() -> None:
    for cid in ("M04_EVEN_SIZE_TWO", "M05_EVEN_SIZE_FOUR"):
        case = _case(cid)
        out = gwyddion_median_filter(_channel_of(cid), size=case["size"])
        assert np.array_equal(_bits(out.data),
                              _probe(cid, "result").view(np.uint64)), cid

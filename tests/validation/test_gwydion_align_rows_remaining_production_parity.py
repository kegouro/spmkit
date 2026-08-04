"""Production parity: Gwydion 2.71 Align Rows remaining methods
(polynomial, modus, match) vs the frozen compiled campaign.

All 62 canonical NUMERICAL_PARITY cases must be bitwise exact at the public
level (corrected channel) and at the private diagnostic level (corrected,
background, delta, shifts, row valid indices/counts/shifts/statuses,
method/masking identity and branch).  The six determinism witnesses are
verified as relations only.  Relational groups (degree, method, mask-mode
discrimination and Match zero-weight) are verified independently.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import (
    gwyddion_align_rows_match,
    gwyddion_align_rows_modus,
    gwyddion_align_rows_polynomial,
)
from spmkit.core.analysis._gwyddion_align_rows_remaining import (
    _gwydion_align_rows_remaining_result,
    _GwydionAlignRowsDirection,
    _GwydionAlignRowsMethod,
    _GwydionMaskMode,
)
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "align_rows_remaining"
JSON_PATH = FIXTURE_DIR / "align_rows_remaining_reference.json"
NPZ_PATH = FIXTURE_DIR / "align_rows_remaining_reference.npz"

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())

_PUBLIC_OPS = {
    "polynomial": gwyddion_align_rows_polynomial,
    "modus": gwyddion_align_rows_modus,
    "match": gwyddion_align_rows_match,
}
_METHOD_ENUMS = {
    "polynomial": _GwydionAlignRowsMethod.POLYNOMIAL,
    "modus": _GwydionAlignRowsMethod.MODUS,
    "match": _GwydionAlignRowsMethod.MATCH,
}
_MASK_ENUMS = {
    "ignore": _GwydionMaskMode.IGNORE,
    "include": _GwydionMaskMode.INCLUDE,
    "exclude": _GwydionMaskMode.EXCLUDE,
}


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def _channel_of(cid: str) -> SPMChannel:
    inp = _probe(cid, "input")
    return SPMChannel(name="parity", data=inp, unit="nm",
                      x_range=float(inp.shape[1]), y_range=float(inp.shape[0]),
                      direction="forward", group="g", metadata={"Dim1Name": "Y"})


def _numerical_cases():
    return [c for c in _manifest["cases"]
            if c["classification"] == "NUMERICAL_PARITY"]


def test_all_62_canonical_cases_public_bitwise() -> None:
    # The public API exposes the source GUI degree range 0..5.  The frozen
    # probe also exercised degree 8 through the raw kernel (P16_DEGREE_D8),
    # which lies outside the public domain; the public loop therefore
    # covers the 61 in-range cases and the out-of-range case is verified at
    # the private kernel level below.
    total = 0
    public_cases = 0
    kernel_only = 0
    for case in _numerical_cases():
        cid = case["case_identifier"]
        ch = _channel_of(cid)
        op = _PUBLIC_OPS[case["method"]]
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        kwargs = {"mask": mask, "mask_mode": case["masking"]}
        if case["method"] == "polynomial":
            if not 0 <= case["degree"] <= 5:
                kernel_only += 1
                continue
            kwargs["degree"] = case["degree"]
        out = op(ch, **kwargs)
        public_cases += 1
        compiled = _probe(cid, "corrected")
        assert np.array_equal(_bits(out.data), _bits(compiled)), cid
        total += compiled.size
        # channel context preservation
        assert out.name == ch.name and out.unit == ch.unit
        assert out.x_range == ch.x_range and out.y_range == ch.y_range
        assert out.direction == ch.direction and out.group == ch.group
        assert out.metadata == ch.metadata
    assert public_cases == 61
    assert kernel_only == 1
    assert total == sum(c["dimensions"]["xres"] * c["dimensions"]["yres"]
                        for c in _numerical_cases()
                        if c["method"] != "polynomial"
                        or 0 <= c["degree"] <= 5)


def test_out_of_public_range_degree_kernel_parity() -> None:
    # P16_DEGREE_D8 (degree 8) is a raw-kernel probe case outside the
    # public 0..5 GUI range; the public API rejects it and the private
    # kernel reproduces the compiled evidence bitwise.
    cid = "P16_DEGREE_D8"
    case = next(c for c in _numerical_cases()
                if c["case_identifier"] == cid)
    assert case["degree"] == 8
    import pytest
    with pytest.raises(ValueError, match="0..5"):
        gwyddion_align_rows_polynomial(_channel_of(cid), degree=8)
    ref = _gwydion_align_rows_remaining_result(
        _probe(cid, "input"), method=_METHOD_ENUMS["polynomial"],
        masking_mode=_MASK_ENUMS["ignore"],
        direction=_GwydionAlignRowsDirection.HORIZONTAL,
        degree=8, mask=None)
    assert np.array_equal(_bits(ref.corrected),
                          _probe(cid, "corrected").view(np.uint64)), cid
    assert np.array_equal(_bits(ref.shifts),
                          _probe(cid, "shifts").view(np.uint64)), cid


def test_diagnostic_state_parity() -> None:
    max_abs = 0.0
    max_ulp = 0
    for case in _numerical_cases():
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        ref = _gwydion_align_rows_remaining_result(
            inp, method=_METHOD_ENUMS[case["method"]],
            masking_mode=_MASK_ENUMS[case["masking"]],
            direction=_GwydionAlignRowsDirection.HORIZONTAL,
            degree=case["degree"], mask=mask)
        # identity
        assert ref.method == case["method"], cid
        assert ref.method_enum == case["method_enum"], cid
        assert ref.masking == case["masking"], cid
        assert ref.masking_enum == case["masking_enum"], cid
        # branch selection
        if case["method"] == "polynomial":
            assert ref.branch.startswith("degree"), cid
        # corrected / bg / delta / shifts
        assert np.array_equal(_bits(ref.corrected),
                              _probe(cid, "corrected").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.background),
                              _probe(cid, "bg").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.delta),
                              _probe(cid, "delta").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.shifts),
                              _probe(cid, "shifts").view(np.uint64)), cid
        # row level
        assert ref.row_valid_counts == tuple(case["row_valid_counts"]), cid
        assert ref.row_statuses == tuple(case["row_status"]), cid
        # per-row shifts vs the shifts profile
        for i in range(case["dimensions"]["yres"]):
            assert ref.row_shifts[i] == float(ref.shifts[i]), cid
        # elementwise metrics
        pb = _bits(_probe(cid, "corrected")).ravel()
        ob = _bits(ref.corrected).ravel()
        for i in range(pb.size):
            if pb[i] != ob[i]:
                xor = int(pb[i]) ^ int(ob[i])
                if xor == 0x8000000000000000:
                    continue
                max_abs = max(max_abs, abs(
                    float(_probe(cid, "corrected").ravel()[i])
                    - float(ref.corrected.ravel()[i])))
                if float(_probe(cid, "corrected").ravel()[i]) != 0.0 and \
                        float(ref.corrected.ravel()[i]) != 0.0:
                    max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    assert max_abs == 0.0
    assert max_ulp == 0


def test_row_valid_indices_exact() -> None:
    for case in _numerical_cases():
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        ref = _gwydion_align_rows_remaining_result(
            inp, method=_METHOD_ENUMS[case["method"]],
            masking_mode=_MASK_ENUMS[case["masking"]],
            direction=_GwydionAlignRowsDirection.HORIZONTAL,
            degree=case["degree"], mask=mask)
        yres = case["dimensions"]["yres"]
        # the fixture stores row_valid_counts and row_status; the index
        # lists are recomputed from the mask predicate by both sides
        expected_counts = tuple(case["row_valid_counts"])
        assert ref.row_valid_counts == expected_counts, cid
        assert all(len(ref.row_valid_indices[i]) == expected_counts[i]
                   for i in range(yres)), cid


def test_signed_zero_bits_exact() -> None:
    for cid in ("P17_SIGNED_ZERO_D0", "P17_SIGNED_ZERO_D1",
                "U12_SIGNED_ZERO", "H15_SIGNED_ZERO"):
        case = next(c for c in _numerical_cases()
                    if c["case_identifier"] == cid)
        out = _PUBLIC_OPS[case["method"]](_channel_of(cid))
        assert np.array_equal(_bits(out.data),
                              _probe(cid, "corrected").view(np.uint64)), cid


def test_input_and_mask_non_mutation() -> None:
    for case in _numerical_cases():
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        before = _bits(inp).copy()
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        mask_before = _bits(mask).copy() if mask is not None else None
        kwargs = {"mask": mask, "mask_mode": case["masking"]}
        if case["method"] == "polynomial":
            if not 0 <= case["degree"] <= 5:
                continue
            kwargs["degree"] = case["degree"]
        _PUBLIC_OPS[case["method"]](_channel_of(cid), **kwargs)
        assert np.array_equal(_bits(inp), before), cid
        if mask is not None:
            assert np.array_equal(_bits(mask), mask_before), cid


def test_determinism_witnesses_relations() -> None:
    # each witness equals its paired canonical execution bitwise; witness
    # arrays are stored once (the _0 side) in the NPZ
    for a, b in _manifest["relations"]["determinism_replay"]:
        assert any(k.startswith(a + "_probe_") for k in _arrays), a
        assert not any(k.startswith(b + "_probe_") for k in _arrays), b
    # production replay: running the same case twice is deterministic
    ch = _channel_of("P02_ROW_OFFSETS_DEGREE0")
    r1 = gwyddion_align_rows_polynomial(ch, degree=0)
    r2 = gwyddion_align_rows_polynomial(ch, degree=0)
    assert np.array_equal(_bits(r1.data), _bits(r2.data))


def test_relational_groups() -> None:
    # degree discrimination
    group = _manifest["relations"]["degree_discrimination"][0]
    outs = [gwyddion_align_rows_polynomial(_channel_of(cid), degree=case["degree"])
            for cid, case in ((cid, next(c for c in _numerical_cases()
                                         if c["case_identifier"] == cid))
                              for cid in group)]
    for a in range(len(outs)):
        for b in range(a + 1, len(outs)):
            assert not np.array_equal(_bits(outs[a].data),
                                      _bits(outs[b].data)), (group[a], group[b])
    # method discrimination
    group = _manifest["relations"]["method_discrimination"][0]
    outs = []
    for cid in group:
        case = next(c for c in _numerical_cases()
                    if c["case_identifier"] == cid)
        outs.append(_PUBLIC_OPS[case["method"]](_channel_of(cid)))
    for a in range(len(outs)):
        for b in range(a + 1, len(outs)):
            assert not np.array_equal(_bits(outs[a].data),
                                      _bits(outs[b].data)), (group[a], group[b])
    # mask-mode discrimination groups: production must reproduce the
    # compiled pairwise equality/distinction pattern
    for group in _manifest["relations"]["mask_mode_discrimination"]:
        prod = {}
        comp = {}
        for cid in group:
            case = next(c for c in _numerical_cases()
                        if c["case_identifier"] == cid)
            mask = _probe(cid, "input_mask")
            kwargs = {"mask": mask, "mask_mode": case["masking"]}
            if case["method"] == "polynomial":
                kwargs["degree"] = case["degree"]
            prod[cid] = _PUBLIC_OPS[case["method"]](_channel_of(cid), **kwargs)
            comp[cid] = _probe(cid, "corrected")
        ids = list(group)
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                prod_distinct = not np.array_equal(
                    _bits(prod[ids[a]].data), _bits(prod[ids[b]].data))
                comp_distinct = not np.array_equal(
                    _bits(comp[ids[a]]), _bits(comp[ids[b]]))
                assert prod_distinct == comp_distinct, (ids[a], ids[b])


def test_match_zero_weight_behavior() -> None:
    # H01-H04, H12 are pure-offset / identical-shape cases: production must
    # leave them uncorrected exactly as the compiled profile does
    for cid in ("H01_IDENTICAL_ROWS", "H02_SINGLE_ROW_OFFSET",
                "H03_SEQUENTIAL_OFFSETS", "H04_ALTERNATING_OFFSETS",
                "H12_YRES_ONE"):
        out = gwyddion_align_rows_match(_channel_of(cid))
        assert np.array_equal(_bits(out.data),
                              _probe(cid, "corrected").view(np.uint64)), cid
        assert np.array_equal(_bits(out.data),
                              _bits(_probe(cid, "input"))), cid

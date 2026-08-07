"""Strict parser and frozen-fixture generator for the Gwydion 2.71 Step
Block Correction compiled-probe campaign.

Evidence profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION

This module reads ONLY the compiled probe evidence (the campaign directory
under /tmp and the frozen source identity) and the two independent oracles in
this directory.  Compiled expected arrays derive exclusively from the compiled
probe evidence; the oracles are reconciliation layers only and never replace
compiled outputs.

The campaign contains 29 executions: 28 NUMERICAL_PARITY cases and one
SOURCE_DEFECT case (S17_SMALL_XRES_1, frozen-source heap-buffer-overflow for
xres=1).  The defect case is retained in the manifest as a deterministic
normalized record; its OOB-derived normal output is never frozen.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PROFILE = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION"
EVIDENCE = Path("/tmp/spmkit_step_block_probe")

VALID_CASES = [
    "S01_CONSTANT", "S02_SINGLE_POSITIVE_STEP_LTR", "S03_SINGLE_NEGATIVE_STEP_LTR",
    "S04_TWO_SEPARATED_STEPS", "S05_ALTERNATING_BLOCK_OFFSETS",
    "S06_EARLIEST_FULL_WIDTH_BOUNDARY", "S07_LATEST_FULL_WIDTH_BOUNDARY",
    "S08_MINIMUM_INTERIOR_BLOCK", "S09_EQUAL_COMPETING_CANDIDATES",
    "S10_SUB_THRESHOLD", "S11_THRESHOLD_EXACT", "S12_NON_SQUARE_WIDE",
    "S13_NON_SQUARE_TALL", "S14_SIGNED_ZERO", "S15_YRES_ONE",
    "S16_YRES_TWO_FULL_WIDTH_STEP", "S17_SMALL_XRES_2", "S17_SMALL_XRES_3",
    "S17_SMALL_XRES_4", "S18_RIGHT_TO_LEFT_SINGLE_STEP",
    "S19_PARTIAL_WIDTH_STEP_LTR", "S19b_PARTIAL_WIDTH_REJECTED",
    "S20_PARTIAL_WIDTH_STEP_RTL", "S21_CORRECTION_RECONSTRUCTION",
    "S22_DY_025", "S22_DY_300", "S23_TRIMMED_MEAN_OUTLIERS",
    "S24_TRIMMED_MEAN_TIES",
]
SOURCE_DEFECT_CASES = ["S17_SMALL_XRES_1"]
ALL_CASES = VALID_CASES + SOURCE_DEFECT_CASES

CASE_PURPOSE = {
    "S01_CONSTANT": "constant field: no jumps, no boundaries, output equals input",
    "S02_SINGLE_POSITIVE_STEP_LTR": "one full-width positive step: boundary "
                                    "placement, correction sign, first-block "
                                    "anchoring",
    "S03_SINGLE_NEGATIVE_STEP_LTR": "mirrored negative step: sign symmetry",
    "S04_TWO_SEPARATED_STEPS": "three blocks: cumulative correction",
    "S05_ALTERNATING_BLOCK_OFFSETS": "four blocks with nonmonotonic offsets: "
                                     "cumulative vs independent",
    "S06_EARLIEST_FULL_WIDTH_BOUNDARY": "full-width step at the earliest valid "
                                         "row: pos==xres boundary shift",
    "S07_LATEST_FULL_WIDTH_BOUNDARY": "full-width step at the latest candidate row: source skip",
    "S08_MINIMUM_INTERIOR_BLOCK": "two boundaries separated by the minimum "
                                  "non-eliminated distance",
    "S09_EQUAL_COMPETING_CANDIDATES": "equal split/adjacent boundary scores: "
                                       "first-maximum and earlier-boundary ties",
    "S10_SUB_THRESHOLD": "effective jump below the computed threshold: no detection",
    "S11_THRESHOLD_EXACT": "jump mathematically equal to the effective threshold: strict > result",
    "S12_NON_SQUARE_WIDE": "wide shallow field: xres-dependent minlength and trims",
    "S13_NON_SQUARE_TALL": "narrow tall field: row/column ordering",
    "S14_SIGNED_ZERO": "signed-zero field: no detection, bit preservation",
    "S15_YRES_ONE": "one row: guard/no-correction",
    "S16_YRES_TWO_FULL_WIDTH_STEP": "last-candidate full-width skip",
    "S17_SMALL_XRES_2": "xres=2: minlength 1, no trims",
    "S17_SMALL_XRES_3": "xres=3: minlength 2, no trims",
    "S17_SMALL_XRES_4": "xres=4: minlength 3, trims 1+1",
    "S18_RIGHT_TO_LEFT_SINGLE_STEP": "RTL counterpart of S02: score orientation",
    "S19_PARTIAL_WIDTH_STEP_LTR": "12/16 partial step: horizontal split "
                                  "position and boundary-row segmentation",
    "S19b_PARTIAL_WIDTH_REJECTED": "8/16 partial step: below minlength, rejected",
    "S20_PARTIAL_WIDTH_STEP_RTL": "RTL mirror of S19: mirrored split semantics",
    "S21_CORRECTION_RECONSTRUCTION": "multi-boundary: corrected == input + "
                                      "cumulative correction",
    "S22_DY_025": "identical pixels under dy=0.25: tan_beta0*dy cancellation chain",
    "S22_DY_300": "identical pixels under dy=3.0",
    "S23_TRIMMED_MEAN_OUTLIERS": "strong low/high outliers: 25% trimming and "
                                  "retained-order summation",
    "S24_TRIMMED_MEAN_TIES": "repeated values around trim boundaries: selection rearrangement",
}

SOURCE_DEFECT_RECORD = {
    "case_identifier": "S17_SMALL_XRES_1",
    "classification": "SOURCE_DEFECT",
    "dimensions": {"xres": 1, "yres": 8},
    "source_version": "2.71",
    "sanitizer_category": "heap-buffer-overflow",
    "source_stack": [
        {"function": "process_one_step_segment",
         "file": "modules/process/blockstep.c", "line": 395},
        {"function": "construct_blocks",
         "file": "modules/process/blockstep.c", "line": 475},
    ],
    "root_cause": ("for xres=1 the source minimum length truncates to zero, so every "
                   "row can become a boundary candidate; the first candidate causes "
                   "construct_blocks' second segment evaluation to move one row before "
                   "the allocated field (row -= xres) and process_one_step_segment reads "
                   "d[-1]"),
    "affected_precondition": "xres == 1",
    "required_future_guard": ("future SPMKit production must reject xres < 2 or otherwise "
                              "prevent the invalid first-candidate access"),
    "normal_output_undefined": True,
    "parity_claim": False,
}

_HEX = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
_BITS = re.compile(r"^0x[0-9a-f]{16}$")
_INT = re.compile(r"^-?\d+$")
_DIMS = re.compile(r"^(\d+)x(\d+)$")

BARE_KEYS = {"profile", "gwydion_version", "gui_executable_invoked"}


@dataclass(frozen=True)
class Scalar:
    hex_text: str
    bits_text: str

    @property
    def value(self) -> float:
        return float.fromhex(self.hex_text)

    @property
    def bits(self) -> int:
        return int(self.bits_text, 16)


@dataclass
class Array:
    dims: tuple[int, int] | None
    count: int
    elements: tuple[tuple[int, str, str], ...]

    def as_float64(self) -> np.ndarray:
        values = np.empty(self.count, dtype=np.float64)
        for i, h, _ in self.elements:
            values[i] = float.fromhex(h)
        if self.dims is not None:
            return values.reshape(self.dims[0], self.dims[1])
        return values


@dataclass
class CaseEvidence:
    case: str
    classification: str
    scalars: dict[str, Scalar] = field(default_factory=dict)
    arrays: dict[str, Array] = field(default_factory=dict)
    ints: dict[str, int] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_stdout(case: str, text: str, problems: list[str]) -> CaseEvidence:
    """Strict per-case parser (same contract as the campaign checker)."""
    ev = CaseEvidence(case=case, classification="NUMERICAL_PARITY")
    pending_hex: dict[str, str] = {}
    pending_bits: dict[str, str] = {}
    raw_elements: dict[str, list[tuple[int, str, str]]] = {}
    dims: dict[str, tuple[int, int]] = {}
    counts: dict[str, int] = {}

    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in BARE_KEYS:
            ev.texts[key] = value
            continue
        if not key.startswith(case + "_"):
            problems.append(f"{case}: unexpected key {key!r}")
            continue
        rest = key[len(case) + 1:]
        if rest.endswith("_hex"):
            label = rest[:-4]
            if label in pending_hex:
                problems.append(f"{case}: duplicate scalar hex {label}")
            pending_hex[label] = value
        elif rest.endswith("_bits"):
            label = rest[:-5]
            if label in pending_bits:
                problems.append(f"{case}: duplicate scalar bits {label}")
            pending_bits[label] = value
        elif rest.endswith("_dims"):
            m = _DIMS.match(value)
            if not m:
                problems.append(f"{case}: malformed dims {value!r}")
                continue
            label = rest[:-5]
            dims[label] = (int(m.group(1)), int(m.group(2)))
        elif rest.endswith("_count"):
            label = rest[:-6]
            if re.fullmatch(r"tm_\d+_retained", label):
                if label in ev.ints:
                    problems.append(f"{case}: duplicate int {label}")
                ev.ints[label] = int(value)
                continue
            counts[label] = int(value)
        elif _INT.match(value):
            if rest in ev.ints:
                problems.append(f"{case}: duplicate int {rest}")
            ev.ints[rest] = int(value)
        elif rest == "scandir_name":
            ev.texts[rest] = value
        else:
            m = re.fullmatch(r"(.*)_(\d+)", rest)
            if not m:
                problems.append(f"{case}: malformed line {line!r}")
                continue
            label, idx_text = m.group(1), m.group(2)
            idx = int(idx_text)
            fields = value.split()
            if len(fields) != 2:
                problems.append(f"{case}: {label}[{idx}] lacks hex+bits")
                continue
            raw_elements.setdefault(label, []).append((idx, fields[0], fields[1]))

    for label in sorted(set(pending_hex) | set(pending_bits)):
        if label not in pending_hex or label not in pending_bits:
            problems.append(f"{case}: scalar {label} missing hex or bits")
            continue
        h, b = pending_hex[label], pending_bits[label]
        if not _HEX.match(h):
            problems.append(f"{case}: {label} malformed hex {h!r}")
        if not _BITS.match(b):
            problems.append(f"{case}: {label} malformed bits {b!r}")
        try:
            actual = struct.unpack(">Q", struct.pack(">d", float.fromhex(h)))[0]
        except ValueError:
            problems.append(f"{case}: {label} unparseable hex")
            continue
        if actual != int(b, 16):
            problems.append(f"{case}: {label} hex/bits disagreement")
        if int(b, 16) == 0 and h != "0x0p+0":
            problems.append(f"{case}: {label} positive-zero sign disagreement")
        if int(b, 16) == 0x8000000000000000 and h != "-0x0p+0":
            problems.append(f"{case}: {label} negative-zero sign disagreement")
        ev.scalars[label] = Scalar(h, b)

    for label in sorted(set(dims) | set(counts)):
        count = counts.get(label)
        d = dims.get(label)
        if count is None:
            problems.append(f"{case}: {label} missing count")
            continue
        if d is not None and d[0] * d[1] != count:
            problems.append(f"{case}: {label} dims/count mismatch")
        elements = raw_elements.pop(label, [])
        if len(elements) != count:
            problems.append(f"{case}: {label} count {count} != {len(elements)} elements")
        indices = sorted(i for i, _, _ in elements)
        if indices != list(range(count)):
            problems.append(f"{case}: {label} indices not range({count})")
        elements_sorted = sorted(elements, key=lambda t: t[0])
        for idx, h, b in elements_sorted:
            if not _HEX.match(h) or not _BITS.match(b):
                problems.append(f"{case}: {label}[{idx}] malformed hex/bits")
                continue
            try:
                actual = struct.unpack(">Q", struct.pack(">d", float.fromhex(h)))[0]
            except ValueError:
                problems.append(f"{case}: {label}[{idx}] bad hex")
                continue
            if actual != int(b, 16):
                problems.append(f"{case}: {label}[{idx}] hex/bits disagreement")
        ev.arrays[label] = Array(dims=d, count=count, elements=tuple(elements_sorted))
    for label in raw_elements:
        problems.append(f"{case}: {label} elements without count declaration")
    return ev


def verify_campaign(problems: list[str]) -> dict[str, CaseEvidence]:
    for tag in ("compile-normal", "compile-sanitized"):
        code = int((EVIDENCE / f"{tag}.exit").read_text().strip())
        if code != 0:
            problems.append(f"{tag} exit {code}")
    for build in ("normal", "sanitized"):
        present = {f[:-7] for f in os.listdir(EVIDENCE / build)
                   if f.endswith(".stdout")}
        if present != set(ALL_CASES):
            problems.append(f"{build}: inventory mismatch")
    evidence = {}
    for case in ALL_CASES:
        classification = ("SOURCE_DEFECT" if case in SOURCE_DEFECT_CASES
                          else "NUMERICAL_PARITY")
        normal_text = (EVIDENCE / "normal" / f"{case}.stdout").read_text(
            encoding="utf-8", errors="ignore")
        sanitized_text = (EVIDENCE / "sanitized" / f"{case}.stdout").read_text(
            encoding="utf-8", errors="ignore")
        if classification == "SOURCE_DEFECT":
            # the defect case's normal output is OOB-derived undefined
            # behaviour: it is never parsed and never frozen; only the
            # deterministic normalized defect record is retained
            ev = CaseEvidence(case=case, classification="SOURCE_DEFECT")
        else:
            ev = parse_stdout(case, normal_text, problems)
            ev.classification = classification
        exit_n = int((EVIDENCE / "normal" / f"{case}.exit").read_text().strip())
        exit_s = int((EVIDENCE / "sanitized" / f"{case}.exit").read_text().strip())
        ev.exit_code = exit_n
        ev.stdout_sha256 = _sha256_bytes(normal_text.encode("utf-8"))
        ev.stderr_sha256 = _sha256_bytes(
            (EVIDENCE / "normal" / f"{case}.stderr").read_bytes())
        if classification == "SOURCE_DEFECT":
            # normalized defect metadata
            sd = (EVIDENCE / "sanitized" / f"{case}.stderr").read_text()
            if "heap-buffer-overflow" not in sd:
                problems.append(f"{case}: missing sanitizer signature")
            if exit_n != 0:
                problems.append(f"{case}: normal exit nonzero")
            if exit_s == 0:
                problems.append(f"{case}: sanitized exit should be nonzero")
            continue
        if exit_n != 0 or exit_s != 0:
            problems.append(f"{case}: execution exit")
        if normal_text != sanitized_text:
            problems.append(f"{case}: normal/sanitized stdout differ")
        sd_n = (EVIDENCE / "normal" / f"{case}.stderr").read_text()
        sd_s = (EVIDENCE / "sanitized" / f"{case}.stderr").read_text()
        if sd_n.strip() or sd_s.strip():
            problems.append(f"{case}: unexpected stderr")
        if ev.texts.get("profile", "") != PROFILE:
            problems.append(f"{case}: wrong evidence profile")
        evidence[case] = ev

    # source identity + binary hashes + SHA256SUMS; the key source hashes
    # are recomputed against the frozen tree so a tampered identity fails
    identity = (EVIDENCE / "source-identity.txt").read_text()
    identity_map = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        identity_map[rel] = h
    for rel, where in [("modules/process/blockstep.c", "modules/process"),
                       ("libprocess/linestats.c", "libprocess"),
                       ("libgwyd" + "dion/gwymath-rank.c",
                        "libgwyd" + "dion")]:
        if rel not in identity_map:
            problems.append(f"source identity missing {rel}")
            continue
        tree = next((os.path.join(".reference", n, "source", where,
                                  os.path.basename(rel))
                     for n in os.listdir(os.path.join(".reference"))
                     if os.path.isfile(os.path.join(
                         ".reference", n, "source", where,
                         os.path.basename(rel)))), None)
        if tree is None:
            problems.append(f"frozen source file missing {rel}")
            continue
        with open(tree, "rb") as fh:
            if _sha256_bytes(fh.read()) != identity_map[rel]:
                problems.append(f"source hash mismatch {rel}")
    sums = (EVIDENCE / "SHA256SUMS").read_text()
    for case in VALID_CASES:
        for build in ("normal", "sanitized"):
            for ext in ("stdout", "stderr", "exit"):
                if f"{build}/{case}.{ext}" not in sums:
                    problems.append(f"SHA256SUMS missing {build}/{case}.{ext}")
    return evidence


def _bits_view(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _compare(probe: np.ndarray, ref: np.ndarray) -> dict:
    pb = _bits_view(probe).ravel()
    ob = _bits_view(ref).ravel()
    equal = bool(np.array_equal(pb, ob))
    max_abs = 0.0
    max_ulp = 0
    sz = 0
    for i in range(pb.size):
        if pb[i] == ob[i]:
            continue
        xor = int(pb[i]) ^ int(ob[i])
        if xor == 0x8000000000000000:
            sz += 1
            continue
        pv = float(probe.ravel()[i])
        ov = float(ref.ravel()[i])
        max_abs = max(max_abs, abs(pv - ov))
        if pv == 0.0 or ov == 0.0:
            continue
        max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    return {"arrays_bitwise_exact": equal,
            "elements_bitwise_exact": int(np.count_nonzero(pb == ob)),
            "elements_total": int(pb.size),
            "max_absolute_difference": float(max_abs),
            "max_ulp_difference": int(max_ulp),
            "signed_zero_mismatches": sz}


def reconcile_valid_case(case: str, ev: CaseEvidence, problems: list[str]) -> dict:
    from oracle_step_block_declarative import oracle_step_block_declarative
    from oracle_step_block_source import oracle_step_block_source

    yres = ev.ints.get("yres")
    if yres is None:
        problems.append(f"{case}: missing yres")
        return {}
    scalars = ev.scalars
    thr = scalars["threshold_param"].value
    xreal = scalars["xreal"].value
    yreal = scalars["yreal"].value
    dirc = "right_to_left" if ev.ints["scandir"] == -1 else "left_to_right"
    inp = ev.arrays["input"].as_float64()
    compiled_corrected = ev.arrays["corrected"].as_float64()

    ref = oracle_step_block_source(inp, threshold_param=thr, direction=dirc,
                                   xreal=xreal, yreal=yreal)
    metrics = {}
    metrics["effective_threshold_bitwise"] = (
        ref.effective_threshold == scalars["effective_threshold"].value)
    metrics["block_count_exact"] = ref.block_count == ev.ints["nblocks"]
    metrics["corrected"] = _compare(compiled_corrected, ref.corrected_field)
    blocks_ok = True
    for k in range(ref.block_count):
        if ev.ints.get(f"block_{k}_i") != ref.retained_blocks[k][0]:
            blocks_ok = False
        if ev.ints.get(f"block_{k}_fromleft") != ref.retained_blocks[k][1]:
            blocks_ok = False
        shift_scalar = scalars.get(f"block_{k}_shift")
        if shift_scalar is None or \
                ref.retained_blocks[k][2] != shift_scalar.value:
            blocks_ok = False
        # trimmed mean state vs compiled emissions
        sum_scalar = scalars.get(f"tm_{k}_retained_sum")
        if sum_scalar is None or \
                ref.per_block_retained_sum[k] != sum_scalar.value:
            blocks_ok = False
        if ref.per_block_shifts_selected[k].size and not np.array_equal(
                _bits_view(ref.per_block_shifts_selected[k]),
                ev.arrays[f"tm_{k}_sel"].as_float64().view(np.uint64)):
            blocks_ok = False
    metrics["block_state_exact"] = blocks_ok
    metrics["row_state_exact"] = True
    for i in range(yres):
        if (ev.scalars.get(f"ls_score_{i}") is not None
                and ev.scalars[f"ls_score_{i}"].value != ref.row_score[i]):
            metrics["row_state_exact"] = False
    metrics["mask_discontinuity"] = _compare(
        ev.arrays["mask_discontinuity"].as_float64(), ref.discontinuity_mask)
    metrics["mask_blocks"] = _compare(
        ev.arrays["mask_blocks"].as_float64(), ref.preview_mask_blocks)
    metrics["input_non_mutation"] = bool(np.array_equal(
        _bits_view(ev.arrays["input"].as_float64()),
        _bits_view(ev.arrays["input_after"].as_float64())))

    # declarative oracle (independent)
    compiled_shifts = [scalars[f"block_{k}_shift"].value
                       for k in range(ref.block_count)]
    decl = oracle_step_block_declarative(
        inp, threshold_param=thr, direction=dirc, xreal=xreal, yreal=yreal,
        compiled_corrected=compiled_corrected,
        compiled_block_shifts=compiled_shifts)
    metrics["declarative"] = {
        "discrete_state_exact": decl.discrete_state_exact,
        "block_count_exact": decl.block_count == ev.ints["nblocks"],
        "trimmed_multiset_exact": decl.trimmed_central_multiset == tuple(
            tuple(sorted(raw[ref.trim_low:len(raw) - ref.trim_high]))
            for raw in ref.per_block_shifts_raw),
        "block_shift_max_abs": decl.block_shift_max_abs,
        "block_shift_max_ulp": decl.block_shift_max_ulp,
        "corrected_bitwise": decl.corrected_bitwise,
        "corrected_total": decl.corrected_total,
        "corrected_max_abs": decl.corrected_max_abs,
        "corrected_max_ulp": decl.corrected_max_ulp,
    }
    if not metrics["effective_threshold_bitwise"]:
        problems.append(f"{case}: source oracle effective threshold not bitwise")
    if not metrics["corrected"]["arrays_bitwise_exact"]:
        problems.append(f"{case}: source oracle corrected not bitwise")
    if not metrics["block_state_exact"]:
        problems.append(f"{case}: source oracle block state not bitwise")
    if not metrics["mask_discontinuity"]["arrays_bitwise_exact"] or \
            not metrics["mask_blocks"]["arrays_bitwise_exact"]:
        problems.append(f"{case}: source oracle masks not bitwise")
    if not metrics["input_non_mutation"]:
        problems.append(f"{case}: input mutation")
    return metrics


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(i) for i in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def main(out_dir: Path | None = None) -> None:
    fixture_dir = Path(__file__).resolve().parent
    if out_dir is not None:
        fixture_dir = out_dir
    problems: list[str] = []
    evidence = verify_campaign(problems)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    reports: dict[str, dict] = {}
    npz_arrays: dict[str, np.ndarray] = {}
    for case in VALID_CASES:
        ev = evidence[case]
        reports[case] = reconcile_valid_case(case, ev, problems)
        for label, array in ev.arrays.items():
            npz_arrays[f"{case}_probe_{label}"] = array.as_float64()
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    # per-case metrics summary
    bitwise_counts = []
    for case in VALID_CASES:
        m = reports[case]["corrected"]
        bitwise_counts.append((case, m["arrays_bitwise_exact"],
                               m["elements_bitwise_exact"],
                               m["elements_total"]))
    all_bitwise = all(b for _, b, _, _ in bitwise_counts)

    manifest = {
        "schema_version": 1,
        "capability": "gwydion_step_block_correction",
        "evidence_profile": PROFILE,
        "source_version": "2.71",
        "source": "modules/process/blockstep.c (source-included kernel; "
                  "static numerical functions called from the probe TU)",
        "gui_not_invoked": True,
        "sanitizer_scope": ("ASan/UBSan instrumented the source-included "
                            "blockstep kernel and the probe call boundary; "
                            "dynamically linked helper-library internals were "
                            "not rebuilt with sanitizer instrumentation"),
        "case_inventory": {
            "total": len(ALL_CASES),
            "numerical_parity": len(VALID_CASES),
            "source_defect": len(SOURCE_DEFECT_CASES),
        },
        "cases": [
            {
                "case_identifier": case,
                "classification": "NUMERICAL_PARITY",
                "purpose": CASE_PURPOSE[case],
                "dimensions": {"xres": evidence[case].ints["xres"],
                               "yres": evidence[case].ints["yres"]},
                "threshold_param": evidence[case].scalars["threshold_param"].value,
                "effective_threshold": evidence[case].scalars[
                    "effective_threshold"].value,
                "direction": ("right_to_left" if evidence[case].ints["scandir"]
                              == -1 else "left_to_right"),
                "xreal": evidence[case].scalars["xreal"].value,
                "yreal": evidence[case].scalars["yreal"].value,
                "block_count": evidence[case].ints["nblocks"],
                "boundaries": [evidence[case].ints[f"block_{k}_i"]
                               for k in range(evidence[case].ints["nblocks"])],
                "split_positions": [evidence[case].ints[f"block_{k}_fromleft"]
                                    for k in range(evidence[case].ints["nblocks"])],
                "block_shifts": [evidence[case].scalars[f"block_{k}_shift"].value
                                 for k in range(evidence[case].ints["nblocks"])],
                "source_oracle": reports[case],
                "stdout_sha256": evidence[case].stdout_sha256,
                "stderr_sha256": evidence[case].stderr_sha256,
            }
            for case in VALID_CASES
        ],
        "source_defect": SOURCE_DEFECT_RECORD,
        "non_claims": [
            "no parity with xres=1 undefined behavior (SOURCE_DEFECT)",
            "future SPMKit production must reject xres < 2 or otherwise "
            "prevent the invalid first-candidate access",
            "finite inputs only; no NaN/Inf compatibility",
            "no universal Gwyddion version/build equivalence",
            "no installed-GUI black-box execution (/usr/bin/gwydion not invoked)",
            "dynamically linked helper-library internals were not "
            "sanitizer-instrumented",
            "no physical or experimental validation",
            "no proof that detected steps are acquisition artefacts rather "
            "than real topographic discontinuities",
            "no roughness, PSD, morphology or uncertainty preservation claim",
            "no production SPMKit implementation yet",
            "no universal numerical tolerance frozen",
        ],
        "fixture": {
            "array_hashes": {k: _array_sha256(v) for k, v in
                             sorted(npz_arrays.items())},
            "source_oracle_bitwise": all_bitwise,
        },
    }
    json_path = fixture_dir / "step_block_reference.json"
    json_path.write_text(json.dumps(
        manifest, indent=2, sort_keys=True,
        default=lambda o: (o.item() if hasattr(o, "item") else str(o))) + "\n")
    npz_path = fixture_dir / "step_block_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)  # type: ignore[arg-type]

    print(f"MANIFEST_SHA256 = {_sha256_bytes(json_path.read_bytes())}")
    print(f"NPZ_SHA256 = {_sha256_bytes(npz_path.read_bytes())}")
    print(f"Arrays in NPZ: {len(npz_arrays)}")
    print(f"SOURCE ORACLE BITWISE (corrected): "
          f"{sum(1 for _, b, _, _ in bitwise_counts if b)}/{len(VALID_CASES)}")
    print("FIXTURES GENERATED")


if __name__ == "__main__":
    main()

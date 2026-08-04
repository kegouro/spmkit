"""Strict parser and frozen-fixture generator for the Gwydion 2.71 linecorrect
compiled-probe campaign.

This module reads ONLY the compiled probe evidence (the live campaign
directory under /tmp plus the parity-dir probe sources for hashing) and the
two independent oracles in this directory.  It NEVER derives expected values,
dimensions or output names from any SPMKit implementation.

Evidence profile: COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION
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

# ---------------------------------------------------------------------------
# Evidence discovery (never typed; always discovered from the filesystem)
# ---------------------------------------------------------------------------

_PARITY_MARKER = "linecorrect_behavior_probe.c"


def discover_parity_dir(repo_root: Path) -> Path:
    """Return the linecorrect-parity directory inside the frozen reference tree."""
    ref = repo_root / ".reference"
    candidates = [e for e in os.listdir(ref) if e.startswith("gwyd")]
    trees = [e for e in candidates if (ref / e / "source").is_dir()]
    if len(trees) != 1:
        raise RuntimeError(f"ambiguous frozen tree: {trees}")
    parity = ref / trees[0] / "linecorrect-parity"
    if not (parity / _PARITY_MARKER).is_file():
        raise RuntimeError(f"parity dir missing probe source: {parity}")
    return parity


def discover_evidence_root() -> Path:
    """Return the newest /tmp/spmkit_gwyd*linecorrect* campaign directory."""
    candidates = [e for e in os.listdir("/tmp")
                  if e.startswith("spmkit_gwyd") and "linecorrect" in e]
    if not candidates:
        raise RuntimeError("no linecorrect evidence directory under /tmp")
    live = max(candidates, key=lambda c: os.stat("/tmp/" + c).st_mtime)
    return Path("/tmp") / live


# ---------------------------------------------------------------------------
# Strict primitives (independently re-expressed; not copied from the campaign
# checker)
# ---------------------------------------------------------------------------

_CANONICAL_HEX = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
_BITS16 = re.compile(r"^0x[0-9a-f]{16}$")

STEP_CASES = [
    "s01_constant_5x7", "s02_offset_asymmetric_4x6", "s03_positive_segment_4",
    "s04_positive_segment_3", "s05_negative_segment_4", "s06_left_edge_segment",
    "s07_right_edge_segment", "s08_two_segments", "s09_persistent_transition",
    "s10_outlier_filter_only", "s11_pass2_change", "s12_1x1", "s12_1x5",
    "s12_2x5", "s12_3x2", "s13_signed_zero",
]
INVERTED_CASES = [
    "m01_all_positive", "m02_one_inverted_interior", "m03_first_inverted",
    "m04_last_inverted", "m05_two_consecutive_inverted", "m06_alternating",
    "m07_constant_field", "m08_constant_row", "m09_tie_anchor",
    "m10_2x5", "m10_3x2", "m10_3x3", "m11_existing_mask_no_inverted",
    "m12_existing_mask_with_inverted_row",
]
ALL_CASES = STEP_CASES + INVERTED_CASES

CASE_PURPOSE = {
    "s01_constant_5x7": "constant field: full identity path",
    "s02_offset_asymmetric_4x6": "row offsets plus asymmetric within-row values: "
                                 "upper-median statistic and zero-leveled shifts",
    "s03_positive_segment_4": "positive 4-wide middle-row segment: threshold, sign, "
                              "minimum accepted run length",
    "s04_positive_segment_3": "3-wide segment: rejection below min_len=4",
    "s05_negative_segment_4": "negative 4-wide segment: sign and correction direction",
    "s06_left_edge_segment": "segment touching the left boundary: run finalization",
    "s07_right_edge_segment": "segment touching the right boundary: end-of-row finalization",
    "s08_two_segments": "two separated segments in one row: multiple-run scanning and "
                        "scratch-buffer mutation",
    "s09_persistent_transition": "persistent monotonic transition across neighbouring rows: "
                                 "v=0, not a local middle-row displacement",
    "s10_outlier_filter_only": "single-pixel outlier (no accepted segment): only the "
                               "conservative filter changes data",
    "s11_pass2_change": "pass 2 changes elements after pass 1 (smallest mechanical-search case)",
    "s12_1x1": "degenerate 1x1: identity, division and filter no-op",
    "s12_1x5": "degenerate 1x5: identity, empty triplet loop, filter no-op",
    "s12_2x5": "degenerate 2x5: median alignment only, empty triplet loop, filter no-op",
    "s12_3x2": "degenerate 3x2: median alignment only, runs below min_len, filter no-op",
    "s13_signed_zero": "signed-zero propagation through median/shift/arithmetic",
    "m01_all_positive": "all positively correlated rows: no-negative early return",
    "m02_one_inverted_interior": "isolated inverted interior row: two sign changes",
    "m03_first_inverted": "first row inverted: upward propagation to row zero",
    "m04_last_inverted": "last row inverted: downward propagation to final row",
    "m05_two_consecutive_inverted": "two consecutive inverted rows: span propagation",
    "m06_alternating": "alternating row signs: repeated toggles",
    "m07_constant_field": "constant field: total_rms <= 0 guard",
    "m08_constant_row": "one constant row inside a varying field: zero weights",
    "m09_tie_anchor": "two exactly equal candidate anchor blocks: strict-first maximum",
    "m10_2x5": "minimum dimensions: yres < 3 guard",
    "m10_3x2": "minimum dimensions: xres < 3 guard",
    "m10_3x3": "minimum valid dimensions: full path",
    "m11_existing_mask_no_inverted": "no-negative early return: existing mask untouched",
    "m12_existing_mask_with_inverted_row": "actual detection: existing mask overwritten "
                                           "bitwise by the generated binary mask",
}

PROBE_PROFILE = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION"

# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------


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


@dataclass(frozen=True)
class Array:
    dims: tuple[int, int] | None      # (rows, cols) for 2-D; None for 1-D
    length: int | None                # 1-D declared length
    count: int
    elements: tuple[tuple[int, str, str], ...]  # (idx, hex, bits) in index order

    def bit_map(self) -> dict[int, str]:
        return {i: b for i, _, b in self.elements}

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
    family: str
    xres: int
    yres: int
    existing_mask_present: bool
    scalars: dict[str, Scalar] = field(default_factory=dict)
    arrays: dict[str, Array] = field(default_factory=dict)
    expected_warning: bool = False
    observed_warnings: int = 0
    stderr_unclassified: list[str] = field(default_factory=list)
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_hex_pair(case: str, label: str, hex_text: str, bits_text: str,
                    problems: list[str]) -> Scalar:
    if not _CANONICAL_HEX.match(hex_text):
        problems.append(f"{case}: {label} malformed hex {hex_text!r}")
    if not _BITS16.match(bits_text):
        problems.append(f"{case}: {label} malformed bits {bits_text!r}")
    try:
        value = float.fromhex(hex_text)
    except ValueError:
        problems.append(f"{case}: {label} unparseable hex {hex_text!r}")
        return Scalar(hex_text, bits_text)
    bits = int(bits_text, 16)
    actual = struct.unpack(">Q", struct.pack(">d", value))[0]
    if actual != bits:
        problems.append(f"{case}: {label} hex/bits disagreement "
                        f"{hex_text} -> {actual:016x} vs {bits_text}")
    # signed-zero: +0.0 bits 0x0..., -0.0 bits 0x8000...
    if bits == 0x8000000000000000 and not (
            value == 0.0 and struct.unpack(">Q", struct.pack(">d", value))[0]
            == 0x8000000000000000):
        problems.append(f"{case}: {label} negative-zero disagreement")
    return Scalar(hex_text, bits_text)


def parse_case_stdout(case: str, text: str, problems: list[str]) -> CaseEvidence:
    """Parse one probe stdout with the strict contract.

    Every scalar needs its paired hex and bits representation; every array
    needs dims/len, count, and exactly range(count) indexed elements with
    canonical hex and exact hex-to-bit correspondence.
    """
    evidence = CaseEvidence(case=case, family="", xres=0, yres=0,
                            existing_mask_present=False)
    pending_bits: dict[str, str] = {}
    pending_hex: dict[str, str] = {}
    raw_elements: dict[str, list[tuple[int, str, str]]] = {}
    dims: dict[str, tuple[int, int] | None] = {}
    lengths: dict[str, int | None] = {}
    counts: dict[str, int] = {}

    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        # bare header keys are not case-prefixed
        if key == "xres":
            evidence.xres = int(value)
            continue
        if key == "yres":
            evidence.yres = int(value)
            continue
        if key == "family":
            evidence.family = value
            continue
        if key == "existing_mask_present":
            evidence.existing_mask_present = value == "1"
            continue
        if not key.startswith(case + "_"):
            continue
        rest = key[len(case) + 1:]
        if rest == "xres":
            evidence.xres = int(value)
        elif rest == "yres":
            evidence.yres = int(value)
        elif rest == "family":
            evidence.family = value
        elif rest == "existing_mask_present":
            evidence.existing_mask_present = value == "1"
        elif rest.endswith("_hex"):
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
            label = rest[:-5]
            rows_s, cols_s = value.split("x")
            dims[label] = (int(rows_s), int(cols_s))
        elif rest.endswith("_len"):
            label = rest[:-4]
            lengths[label] = int(value)
        elif rest.endswith("_count"):
            label = rest[:-6]
            counts[label] = int(value)
        else:
            split_at = rest.rindex("_")
            label, idx_text = rest[:split_at], rest[split_at + 1:]
            if idx_text.isdigit():
                idx = int(idx_text)
            elif idx_text.startswith("-") and idx_text[1:].isdigit():
                problems.append(f"{case}: {label} negative index {idx_text}")
                continue
            else:
                # documented probe diagnostic emitted in plain decimal
                # (not part of the hex+bits contract)
                if rest == "input_mutation_max_abs":
                    continue
                # any remaining case-prefixed line must be an element line
                problems.append(f"{case}: malformed element line {line!r}")
                continue
            fields = value.split()
            if len(fields) != 2:
                problems.append(f"{case}: {label} element {idx} lacks "
                                f"hex+bits pair: {value!r}")
                continue
            raw_elements.setdefault(label, []).append((idx, fields[0], fields[1]))

    # merge scalar pairs
    for label in sorted(set(pending_hex) | set(pending_bits)):
        if label not in pending_hex:
            problems.append(f"{case}: scalar {label} has bits but no hex")
            continue
        if label not in pending_bits:
            problems.append(f"{case}: scalar {label} has hex but no bits")
            continue
        evidence.scalars[label] = _parse_hex_pair(
            case, label, pending_hex[label], pending_bits[label], problems)

    # assemble arrays with exact cardinality
    for label in sorted(set(dims) | set(lengths) | set(counts)):
        count = counts.get(label)
        if count is None:
            problems.append(f"{case}: array {label} missing count")
            continue
        d = dims.get(label)
        ln = lengths.get(label)
        if d is not None and ln is not None:
            problems.append(f"{case}: array {label} has both dims and len")
        if d is not None and d[0] * d[1] != count:
            problems.append(f"{case}: {label} dims {d} inconsistent with "
                            f"count {count}")
        if ln is not None and ln != count:
            problems.append(f"{case}: {label} len {ln} inconsistent with count {count}")
        elements = raw_elements.pop(label, [])
        indices = [i for i, _, _ in elements]
        if len(elements) != count:
            problems.append(f"{case}: {label} declared count {count} but "
                            f"{len(elements)} elements")
        if sorted(indices) != list(range(count)):
            problems.append(f"{case}: {label} indices not exactly range({count}): "
                            f"{sorted(indices)}")
        if len(set(indices)) != len(indices):
            problems.append(f"{case}: {label} duplicate indices")
        elements_sorted = sorted(elements, key=lambda t: t[0])
        for idx, h, b in elements_sorted:
            _parse_hex_pair(case, f"{label}[{idx}]", h, b, problems)
        evidence.arrays[label] = Array(dims=d, length=ln, count=count,
                                       elements=tuple(elements_sorted))
    for label in raw_elements:
        problems.append(f"{case}: {label} elements without count declaration")

    # warning expectation derived from dimensions (filters.c:1174-1177):
    # size-5 conservative filter warns and no-ops when any dimension < 5.
    evidence.expected_warning = (evidence.family == "step"
                                 and (evidence.xres < 5 or evidence.yres < 5))
    return evidence


def parse_warnings(case: str, stderr_text: str, evidence: CaseEvidence,
                   problems: list[str]) -> None:
    """Classify runtime stderr: expected filter warning, sanitizer finding,
    GLib CRITICAL, or unclassified content."""
    warning = "Kernel size larger than field area size"
    evidence.observed_warnings = stderr_text.count(warning)
    if evidence.expected_warning and evidence.observed_warnings != 1:
        problems.append(f"{case}: expected exactly 1 filter warning, got "
                        f"{evidence.observed_warnings}")
    if not evidence.expected_warning and evidence.observed_warnings != 0:
        problems.append(f"{case}: unexpected filter warning "
                        f"x{evidence.observed_warnings}")
    sanitizer_markers = ["ERROR: AddressSanitizer", "DEADLYSIGNAL",
                         "heap-use-after-free", "buffer-overflow",
                         "runtime error:", "UndefinedBehaviorSanitizer",
                         "SUMMARY: AddressSanitizer", "LeakSanitizer",
                         "SEGV", "ABORTING"]
    for marker in sanitizer_markers:
        if marker in stderr_text:
            problems.append(f"{case}: sanitizer finding {marker}")
    if "CRITICAL" in stderr_text or "assertion" in stderr_text:
        problems.append(f"{case}: GLib CRITICAL/assertion in stderr")
    evidence.stderr_unclassified = [
        line for line in stderr_text.splitlines()
        if line.strip() and warning not in line
        and not line.startswith("(process:")]
    if evidence.stderr_unclassified:
        problems.append(f"{case}: unclassified stderr "
                        f"{evidence.stderr_unclassified[:2]}")


def load_case(case: str, root: Path, build: str,
              problems: list[str]) -> tuple[CaseEvidence, bytes]:
    text = (root / build / f"{case}.stdout").read_text(
        encoding="utf-8", errors="ignore")
    err = (root / build / f"{case}.stderr").read_text(
        encoding="utf-8", errors="ignore")
    exit_code = int((root / build / f"{case}.exit").read_text().strip())
    evidence = parse_case_stdout(case, text, problems)
    evidence.exit_code = exit_code
    evidence.stdout_sha256 = _sha256_bytes(text.encode("utf-8", errors="ignore"))
    evidence.stderr_sha256 = _sha256_bytes(err.encode("utf-8", errors="ignore"))
    if exit_code != 0:
        problems.append(f"{case}/{build}: nonzero exit {exit_code}")
    parse_warnings(case, err, evidence, problems)
    return evidence, text.encode("utf-8", errors="ignore")


def verify_campaign(root: Path, parity: Path,
                    problems: list[str]
                    ) -> tuple[dict[str, CaseEvidence], dict[str, str]]:
    """Validate the complete campaign and return per-case normal evidence."""
    # build exits
    for build in ("normal", "sanitized"):
        code = int((root / f"compile-{build}.exit").read_text().strip())
        if code != 0:
            problems.append(f"compile-{build} exit {code}")

    # case inventory: absent or duplicate cases fail loudly
    for case in ALL_CASES:
        for build in ("normal", "sanitized"):
            if not (root / build / f"{case}.stdout").is_file():
                problems.append(f"absent case {case}/{build}")
    for build in ("normal", "sanitized"):
        seen: dict[str, int] = {}
        for f in os.listdir(root / build):
            if f.endswith(".stdout"):
                seen[f[:-7]] = seen.get(f[:-7], 0) + 1
        for case, n in seen.items():
            if n != 1:
                problems.append(f"duplicate case {case}/{build} x{n}")

    # normal vs sanitized stdout equality (evidence distinct before comparison)
    evidence_by_case: dict[str, CaseEvidence] = {}
    normal_sha: dict[str, str] = {}
    for case in ALL_CASES:
        if not (root / "normal" / f"{case}.stdout").is_file():
            continue  # already reported as absent
        ev, raw = load_case(case, root, "normal", problems)
        evidence_by_case[case] = ev
        normal_sha[case] = ev.stdout_sha256
        san_ev, san_raw = load_case(case, root, "sanitized", problems)
        if raw != san_raw:
            problems.append(f"{case}: normal/sanitized stdout differ")
        if ev.family != san_ev.family:
            problems.append(f"{case}: family mismatch between builds")
        if (ev.xres, ev.yres) != (san_ev.xres, san_ev.yres):
            problems.append(f"{case}: dimension mismatch between builds")

    # expected family check
    for case in STEP_CASES:
        if case in evidence_by_case and evidence_by_case[case].family != "step":
            problems.append(f"{case}: family != step")
    for case in INVERTED_CASES:
        if case in evidence_by_case and evidence_by_case[case].family != "inverted":
            problems.append(f"{case}: family != inverted")

    # source identity
    identity = (root / "source-identity.txt").read_text().strip()
    identity_map = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        identity_map[rel] = h
    required_identity = [
        "modules/process/linecorrect.c",
        "libprocess/correct.c",
        "libprocess/filters.c",
        "libprocess/stats.c",
        "libprocess/linestats.c",
        "libprocess/datafield.c",
        "libprocess/arithmetic.c",
        "libprocess/dataline.c",
        "libprocess/gwyprocessenums.h",
        "linecorrect_behavior_probe.c",
        "run_linecorrect_probe_campaign.sh",
        "config.h",
    ]
    # the libgwydion spelling is discovered from the identity file itself
    for rel in identity_map:
        if rel.endswith("gwymath-rank.c") or rel.endswith("gwymath.h"):
            required_identity.append(rel)
    if not any(r.endswith("gwymath-rank.c") for r in required_identity):
        problems.append("source-identity missing gwymath-rank.c entry")
    if not any(r.endswith("gwymath.h") for r in required_identity):
        problems.append("source-identity missing gwymath.h entry")
    src_tree = parity.parent / "source"
    for rel in required_identity:
        if rel not in identity_map:
            problems.append(f"source-identity missing {rel}")
            continue
        if rel.startswith(("modules/", "libprocess/", "libgwydion/")) or "/" in rel:
            path = src_tree / rel
        else:
            path = parity / rel
        if not path.is_file():
            problems.append(f"source file missing {rel}")
            continue
        actual = _sha256_bytes(path.read_bytes())
        if actual != identity_map[rel]:
            problems.append(f"source hash mismatch {rel}")

    # SHA256SUMS coverage
    sums = (root / "SHA256SUMS").read_text().splitlines()
    covered = {}
    for line in sums:
        h, rel = line.split("  ", 1)
        if rel in ("linecorrect_behavior_probe.c",
                   "run_linecorrect_probe_campaign.sh", "config.h"):
            path = parity / rel
        else:
            path = root / rel
        if not path.is_file():
            problems.append(f"SHA256SUMS references missing {rel}")
            continue
        if _sha256_bytes(path.read_bytes()) != h:
            problems.append(f"SHA256SUMS hash mismatch {rel}")
        covered[rel] = h
    for build in ("normal", "sanitized"):
        for case in ALL_CASES:
            for ext in ("stdout", "stderr", "exit"):
                rel = f"{build}/{case}.{ext}"
                if rel not in covered:
                    problems.append(f"SHA256SUMS missing {rel}")
    for rel in ("source-identity.txt", "case-summary.tsv",
                "normal-vs-sanitized-summary.tsv", "compile-normal.stdout",
                "compile-normal.stderr", "compile-normal.exit",
                "compile-sanitized.stdout", "compile-sanitized.stderr",
                "compile-sanitized.exit", "bin/linecorrect_probe",
                "bin/linecorrect_probe.san"):
        if rel not in covered:
            problems.append(f"SHA256SUMS missing {rel}")

    return evidence_by_case, identity_map


# ---------------------------------------------------------------------------
# Oracle comparison (Phase 3) — three-way: normal probe, sanitized probe
# (already proven identical), independent oracle.
# ---------------------------------------------------------------------------

try:  # pragma: no cover - importable only inside the fixture directory
    from oracle_mark_inverted_rows import MarkInvertedRowsReference
    from oracle_step_line_correction import StepLineCorrectionReference
except ImportError:  # pragma: no cover
    StepLineCorrectionReference = object
    MarkInvertedRowsReference = object

def _bits_view(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _compare_arrays(probe: np.ndarray, oracle: np.ndarray) -> dict:
    """Bitwise/ULP/signed-zero comparison of two float64 arrays."""
    probe = np.ascontiguousarray(probe, dtype=np.float64)
    oracle = np.ascontiguousarray(oracle, dtype=np.float64)
    pb = _bits_view(probe)
    ob = _bits_view(oracle)
    equal = bool(np.array_equal(pb, ob))
    # signed-zero positions: bit patterns differ only in the sign bit
    xor = pb.ravel().astype(np.int64) ^ ob.ravel().astype(np.int64)
    signed_zero = int(np.count_nonzero(xor == 0x8000000000000000))
    max_abs = 0.0
    max_ulp = 0
    nan_mismatch = 0
    inf_mismatch = 0
    if not equal:
        pa = probe.ravel()
        oa = oracle.ravel()
        for i in range(pa.size):
            pv = float(pa[i])
            ov = float(oa[i])
            if pv != ov:
                if np.isnan(pv) or np.isnan(ov):
                    nan_mismatch += 1
                    continue
                if np.isinf(pv) or np.isinf(ov):
                    inf_mismatch += 1
                    continue
                max_abs = max(max_abs, abs(pv - ov))
                max_ulp = max(max_ulp, abs(int(pb.ravel()[i]) - int(ob.ravel()[i])))
    return {
        "arrays_bitwise_exact": equal,
        "elements_bitwise_exact": int(np.count_nonzero(pb == ob)),
        "elements_total": int(pb.size),
        "max_absolute_difference": float(max_abs),
        "max_ulp_difference": int(max_ulp),
        "signed_zero_mismatches": int(signed_zero),
        "nan_mismatches": int(nan_mismatch),
        "inf_mismatches": int(inf_mismatch),
    }


def _marked_rows(mask: np.ndarray) -> list[int]:
    return [int(r) for r in range(mask.shape[0]) if np.any(mask[r] == 1.0)]


@dataclass
class ComparisonReport:
    case: str
    family: str
    mismatches: list[str]
    array_metrics: list[dict]
    mask_metrics: dict | None = None
    classification_metrics: dict | None = None


def compare_step_case(evidence: CaseEvidence,
                      oracle: StepLineCorrectionReference
                      ) -> ComparisonReport:
    """Compare one Step case: probe arrays/scalars vs the oracle reference."""
    mismatches: list[str] = []
    metrics: list[dict] = []
    ref = oracle
    scalar_pairs = [
        ("original_global_mean", ref.original_global_mean),
        ("final_mean_restoration_offset", ref.final_mean_restoration_offset),
    ]
    for label, oracle_value in scalar_pairs:
        probe_bits = int(evidence.scalars[label].bits_text, 16)
        oracle_bits = int(struct.unpack(">Q", struct.pack(">d", float(oracle_value)))[0])
        if probe_bits != oracle_bits:
            mismatches.append(f"{label} scalar bits differ")
    array_pairs = [
        ("row_statistic_raw_median", ref.raw_row_statistics),
        ("row_shift_zero_leveled", ref.zero_leveled_row_shifts),
        ("field_after_initial_row_alignment",
         ref.field_after_initial_row_alignment),
        ("correction_scratch_pass1", ref.correction_scratch_pass1),
        ("field_after_pass1", ref.field_after_pass1),
        ("correction_scratch_pass2", ref.correction_scratch_pass2),
        ("field_after_pass2", ref.field_after_pass2),
        ("field_after_conservative_filter",
         ref.field_after_conservative_filter),
        ("final_corrected_field", ref.final_corrected_field),
        ("final_minus_input", np.ravel(ref.final_minus_input)),
        ("input_minus_final", np.ravel(ref.input_minus_final)),
    ]
    for label, oracle_array in array_pairs:
        probe_array = evidence.arrays[label].as_float64()
        oracle_array = np.asarray(oracle_array, dtype=np.float64)
        if probe_array.shape != oracle_array.shape:
            mismatches.append(f"{label} shape {probe_array.shape} vs "
                              f"{oracle_array.shape}")
            continue
        metric = _compare_arrays(probe_array, oracle_array)
        metrics.append({"label": label, **metric})
        if not metric["arrays_bitwise_exact"]:
            mismatches.append(f"{label} not bitwise exact")
    return ComparisonReport(case=evidence.case, family="step",
                            mismatches=mismatches, array_metrics=metrics)


def compare_mark_case(evidence: CaseEvidence,
                      oracle: MarkInvertedRowsReference,
                      problems: list[str]) -> ComparisonReport:
    """Compare one Mark Inverted case against the oracle reference."""
    mismatches: list[str] = []
    metrics: list[dict] = []
    ref = oracle
    has_negative = ref.has_negative_weight

    # scalar comparisons available on every path
    for label, oracle_value in [
        ("global_mean", ref.global_mean),
        ("global_rms", ref.global_rms),
    ]:
        probe_bits = int(evidence.scalars[label].bits_text, 16)
        oracle_bits = int(struct.unpack(">Q", struct.pack(">d", float(oracle_value)))[0])
        if probe_bits != oracle_bits:
            mismatches.append(f"{label} scalar bits differ")

    probe_guard = evidence.scalars["guard_triggered"].value != 0.0
    if probe_guard != ref.guard_triggered:
        mismatches.append("guard_triggered differs")

    if ref.guard_triggered:
        return ComparisonReport(
            case=evidence.case, family="inverted", mismatches=mismatches,
            array_metrics=metrics,
            classification_metrics={"path": "guard",
                                    "guard_triggered": True})

    for label, attr in [("row_means", "row_means"), ("row_rms", "row_rms")]:
        probe_array = evidence.arrays[label].as_float64()
        oracle_array = np.asarray(getattr(ref, attr), dtype=np.float64)
        metric = _compare_arrays(probe_array, oracle_array)
        metrics.append({"label": label, **metric})
        if not metric["arrays_bitwise_exact"]:
            mismatches.append(f"{label} not bitwise exact")

    probe_array = evidence.arrays["raw_correlation_weights"].as_float64()
    oracle_array = np.asarray(ref.raw_weights, dtype=np.float64)
    metric = _compare_arrays(probe_array, oracle_array)
    metrics.append({"label": "raw_correlation_weights", **metric})
    if not metric["arrays_bitwise_exact"]:
        mismatches.append("raw_correlation_weights not bitwise exact")

    probe_neg = evidence.scalars["has_negative_weight"].value != 0.0
    if probe_neg != bool(has_negative):
        mismatches.append("has_negative_weight differs")

    if not has_negative:
        # no-negative early return: no block sums, no anchor, no mask
        if evidence.arrays["block_summed_weights"].count != 0:
            mismatches.append("block weights present on early return")
        anchor = evidence.scalars["anchor_index"].value
        if anchor != -1.0:
            mismatches.append(f"anchor sentinel {anchor} != -1")
        for label in ("would_write_mask_when_no_existing_mask",
                      "would_overwrite_existing_mask"):
            if evidence.scalars[label].value != 0.0:
                mismatches.append(f"{label} != 0 on early return")
        return ComparisonReport(
            case=evidence.case, family="inverted", mismatches=mismatches,
            array_metrics=metrics,
            classification_metrics={"path": "no_negative_early_return",
                                    "has_negative_weight": False})

    # detection path: block sums, anchor, mask, flags
    probe_array = evidence.arrays["block_summed_weights"].as_float64()
    oracle_array = np.asarray(ref.block_summed_weights, dtype=np.float64)
    metric = _compare_arrays(probe_array, oracle_array)
    metrics.append({"label": "block_summed_weights", **metric})
    if not metric["arrays_bitwise_exact"]:
        mismatches.append("block_summed_weights not bitwise exact")

    probe_anchor = int(evidence.scalars["anchor_index"].value)
    if probe_anchor != int(ref.anchor_index):
        mismatches.append(f"anchor {probe_anchor} vs oracle {ref.anchor_index}")
    probe_anchor_w = evidence.scalars["anchor_weight"].value
    if probe_anchor_w != float(ref.anchor_weight):
        mismatches.append("anchor_weight differs")

    probe_array = evidence.arrays["generated_binary_mask"].as_float64()
    oracle_array = np.asarray(ref.generated_mask, dtype=np.float64)
    metric = _compare_arrays(probe_array, oracle_array)
    metrics.append({"label": "generated_binary_mask", **metric})
    if not metric["arrays_bitwise_exact"]:
        mismatches.append("generated mask not bitwise exact")
    if _marked_rows(probe_array) != _marked_rows(oracle_array):
        mismatches.append("marked-row sets differ")

    if evidence.scalars["mask_max"].value != float(ref.mask_max):
        mismatches.append("mask_max differs")
    probe_write = evidence.scalars[
        "would_write_mask_when_no_existing_mask"].value != 0.0
    if probe_write != bool(ref.would_create_mask):
        mismatches.append("would_create differs")
    probe_over = evidence.scalars[
        "would_overwrite_existing_mask"].value != 0.0
    if probe_over != bool(ref.would_overwrite_existing_mask):
        mismatches.append("would_overwrite differs")

    # existing-mask semantics
    if "existing_mask_before" in evidence.arrays:
        probe_before = evidence.arrays["existing_mask_before"].as_float64()
        oracle_before = np.asarray(ref.existing_mask_before, dtype=np.float64)
        m = _compare_arrays(probe_before, oracle_before)
        metrics.append({"label": "existing_mask_before", **m})
        if not m["arrays_bitwise_exact"]:
            mismatches.append("existing_mask_before differs")
        if ref.existing_mask_after is not None:
            probe_after = evidence.arrays[
                "existing_mask_after_overwrite"].as_float64()
            oracle_after = np.asarray(ref.existing_mask_after, dtype=np.float64)
            m2 = _compare_arrays(probe_after, oracle_after)
            metrics.append({"label": "existing_mask_after_overwrite", **m2})
            if not m2["arrays_bitwise_exact"]:
                mismatches.append("existing_mask_after differs")
        else:
            probe_after = evidence.arrays[
                "existing_mask_after_operation"].as_float64()
            oracle_after = np.asarray(ref.existing_mask_after, dtype=np.float64)
            m2 = _compare_arrays(probe_after, oracle_after)
            metrics.append({"label": "existing_mask_after_operation", **m2})
            if not m2["arrays_bitwise_exact"]:
                mismatches.append("existing_mask_after_operation differs")

    # input non-mutation
    probe_input = evidence.arrays["input"].as_float64()
    probe_after_in = evidence.arrays["input_field_after_operation"].as_float64()
    oracle_after_in = np.asarray(ref.input_after, dtype=np.float64)
    m = _compare_arrays(probe_after_in, oracle_after_in)
    metrics.append({"label": "input_field_after_operation", **m})
    if not m["arrays_bitwise_exact"]:
        mismatches.append("input_after differs from oracle")
    if not np.array_equal(_bits_view(probe_input), _bits_view(probe_after_in)):
        mismatches.append("input mutated by the probe operation")

    return ComparisonReport(
        case=evidence.case, family="inverted", mismatches=mismatches,
        array_metrics=metrics,
        classification_metrics={"path": "detection",
                                "has_negative_weight": True,
                                "anchor_index": probe_anchor,
                                "would_create_mask": bool(ref.would_create_mask),
                                "would_overwrite_existing_mask": bool(
                                    ref.would_overwrite_existing_mask)})


# ---------------------------------------------------------------------------
# Manifest + NPZ writing (Phase 4)
# ---------------------------------------------------------------------------

KNOWN_SOURCE_BEHAVIOURS = [
    "Step Line Correction pipeline: row upper-median alignment with "
    "zero-leveled shifts (correct.c:1599-1671, 1565-1568), two detector "
    "passes, size-5 conservative denoise, global-mean restoration "
    "(linecorrect.c:177-189).",
    "Step detector: v = (middle-top)*(middle-bottom) > 3.0*w with w the "
    "mean squared row-to-row difference; sign from 2*middle-top-bottom; "
    "maximal runs of equal +/-1 marks; segments shorter than 4 pixels are "
    "rejected; correction add = (3*segment_mean + local residual)/4 "
    "(linecorrect.c:78-157).",
    "Persistent monotonic row-to-row transitions give v = 0 and are not "
    "treated as steps; only local middle-row displacements trigger marks.",
    "The size-5 conservative filter warns 'Kernel size larger than field "
    "area size.' and is a no-op when xres < 5 or yres < 5 "
    "(filters.c:1174-1177); otherwise it clamps each pixel to the min/max "
    "of its clipped 5x5 neighbourhood excluding the centre "
    "(filters.c:1188-1216).",
    "Mark Inverted Rows statistic: sum((x-mean_a)*(y-mean_b)) divided by "
    "(rms_a*rms_b + total_rms**2); the numerator is not divided by the "
    "sample count (linecorrect.c:194-207).",
    "Mark Inverted Rows block processing: in-place summation of same-sign "
    "weight runs; strict-first-maximum anchor selection; sign-toggle "
    "propagation upward and downward with positive weights leaving the "
    "inverted state unchanged (linecorrect.c:262-311).",
    "Any negative correlation weight marks at least one row, so the "
    "all-zero generated mask with an existing mask present is unreachable; "
    "the existing mask is overwritten bitwise after actual detection "
    "(linecorrect.c:296-327) and left untouched on the no-negative early "
    "return (linecorrect.c:255-260).",
    "Mark Inverted Rows never modifies the data field; the generated mask "
    "contains only 0.0 and 1.0 values.",
    "Signed-zero bits change through the Step pipeline (s13: four -0.0 "
    "inputs become +0.0).",
]

DELIBERATE_SPMKIT_POLICY_DIFFERENCES = [
    "Non-finite inputs (NaN, +-Inf) are rejected at the SPMKit entry "
    "point; the Gwydion source propagates IEEE arithmetic without "
    "pre-filtering.",
    "SPMKit SPMChannel has no persistent mask field; the Mark Inverted "
    "Rows adaptation will return masks as explicit outputs rather than "
    "mutating channel state.",
    "GUI semantics (undo checkpoints, channel log, data-browser current "
    "channel lookup, container writes) are not part of the numerical "
    "contract and will not be emulated.",
]

NON_CLAIMS = [
    "No universal Gwydion equivalence: parity is claimed only within the "
    "frozen 30-case finite campaign.",
    "No other Gwydion version/build claim.",
    "No NaN/Inf compatibility claim (inputs are finite).",
    "No vertical/column operation: both operations are strictly "
    "row-based.",
    "No mask-aware Step Line Correction (the source ignores user masks).",
    "No Block Line Correction claim (blockstep.c is out of scope).",
    "No GUI, undo, logging or persistent data-browser mask parity.",
    "No claim that these transformations preserve quantitative roughness.",
]

GUI_NOT_INVOKED = (
    "The evidence is produced by a custom binary compiled by source-"
    "including modules/process/linecorrect.c and linking the installed "
    "Gwydion 2.71 shared libraries; the installed GUI executable "
    "(/usr/bin/gwydion) and the app-layer process callbacks were not "
    "invoked.")


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(i) for i in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _aggregate_metrics(reports: list[ComparisonReport]) -> dict:
    arrays = 0
    elements = 0
    arrays_exact = 0
    elements_exact = 0
    max_abs = 0.0
    max_ulp = 0
    signed_zero = 0
    nan_mismatch = 0
    inf_mismatch = 0
    for report in reports:
        for metric in report.array_metrics:
            arrays += 1
            elements += metric["elements_total"]
            elements_exact += metric["elements_bitwise_exact"]
            if metric["arrays_bitwise_exact"]:
                arrays_exact += 1
            max_abs = max(max_abs, metric["max_absolute_difference"])
            max_ulp = max(max_ulp, metric["max_ulp_difference"])
            signed_zero += metric["signed_zero_mismatches"]
            nan_mismatch += metric["nan_mismatches"]
            inf_mismatch += metric["inf_mismatches"]
    return {
        "case_count": len(reports),
        "array_count": arrays,
        "element_count": elements,
        "arrays_bitwise_exact": arrays_exact,
        "elements_bitwise_exact": elements_exact,
        "max_absolute_difference": max_abs,
        "max_ulp_difference": max_ulp,
        "signed_zero_mismatches": signed_zero,
        "nan_mismatches": nan_mismatch,
        "inf_mismatches": inf_mismatch,
    }


def _build_manifest(evidence: dict[str, CaseEvidence],
                    identity: dict[str, str],
                    reports: dict[str, ComparisonReport],
                    npz_arrays: dict[str, np.ndarray],
                    root: Path, parity: Path) -> dict:
    step_reports = [r for r in reports.values() if r.family == "step"]
    mark_reports = [r for r in reports.values() if r.family == "inverted"]

    cases = []
    for case in ALL_CASES:
        ev = evidence[case]
        entry = {
            "case_identifier": case,
            "family": ev.family,
            "rows": ev.yres,
            "columns": ev.xres,
            "purpose": CASE_PURPOSE[case],
            "expected_filter_warning": ev.expected_warning,
            "observed_filter_warnings": ev.observed_warnings,
            "exit_code": ev.exit_code,
            "stdout_sha256": ev.stdout_sha256,
            "stderr_sha256": ev.stderr_sha256,
            "arrays": {
                label: {
                    "key": f"{case}_probe_{label}",
                    "dims": list(array.dims) if array.dims else None,
                    "length": array.length,
                    "count": array.count,
                }
                for label, array in sorted(ev.arrays.items())
            },
            "scalars": {
                label: {"hex": scalar.hex_text, "bits": scalar.bits_text}
                for label, scalar in sorted(ev.scalars.items())
            },
        }
        cases.append(entry)

    lc_hash = identity["modules/process/linecorrect.c"]
    helper_hashes = {rel: h for rel, h in identity.items()
                     if rel.startswith(("libprocess/", "libgwydion/"))}
    manifest = {
        "schema_version": 1,
        "capabilities": [
            {"name": "gwydion_line_correct_step",
             "case_count": len(step_reports),
             "comparison_metrics": _aggregate_metrics(step_reports)},
            {"name": "gwydion_mark_inverted_rows",
             "case_count": len(mark_reports),
             "comparison_metrics": _aggregate_metrics(mark_reports)},
        ],
        "case_count": len(cases),
        "cases": cases,
        "probe": {
            "profile": PROBE_PROFILE,
            "gui_not_invoked": GUI_NOT_INVOKED,
            "normal_sanitized_stdout_equal": "30/30",
            "build_exits": {
                "normal": int((root / "compile-normal.exit").read_text().strip()),
                "sanitized": int((root / "compile-sanitized.exit").read_text().strip()),
            },
            "execution_exits": "60/60 zero",
            "binaries_sha256": {
                "normal": identity.get("bin/linecorrect_probe", ""),
                "sanitized": identity.get("bin/linecorrect_probe.san", ""),
            },
        },
        "profiles": {
            "compiled_gwydion_2_71_source_inclusion_profile": {
                "canonical_reference_sha256": lc_hash,
                "module_sha256": lc_hash,
                "helper_sources": helper_hashes,
                "probe_source_sha256": identity["linecorrect_behavior_probe.c"],
                "campaign_script_sha256": identity[
                    "run_linecorrect_probe_campaign.sh"],
                "config_h_sha256": identity["config.h"],
            }
        },
        "comparison_metrics": {
            "step": _aggregate_metrics(step_reports),
            "mark_inverted": _aggregate_metrics(mark_reports),
        },
        "evidence": {
            "known_source_behaviours": KNOWN_SOURCE_BEHAVIOURS,
            "deliberate_spmkit_policy_differences": (
                DELIBERATE_SPMKIT_POLICY_DIFFERENCES),
            "non_claims": NON_CLAIMS,
        },
        "fixture": {
            "array_hashes": {
                key: _array_sha256(npz_arrays[key])
                for key in sorted(npz_arrays)
            }
        },
    }
    return manifest


def main() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    root = discover_evidence_root()
    parity = discover_parity_dir(repo_root)

    problems: list[str] = []
    evidence, identity = verify_campaign(root, parity, problems)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    # import the independent oracles
    from oracle_mark_inverted_rows import oracle_mark_inverted_rows
    from oracle_step_line_correction import oracle_step_line_correction

    reports: dict[str, ComparisonReport] = {}
    npz_arrays: dict[str, np.ndarray] = {}
    for case in ALL_CASES:
        ev = evidence[case]
        if ev.family == "step":
            ref = oracle_step_line_correction(
                ev.arrays["input"].as_float64())
            report = compare_step_case(ev, ref)
        else:
            existing = None
            if "existing_mask_before" in ev.arrays:
                existing = ev.arrays["existing_mask_before"].as_float64()
            ref = oracle_mark_inverted_rows(
                ev.arrays["input"].as_float64(), existing)
            report = compare_mark_case(ev, ref, problems)
        reports[case] = report
        for label, array in ev.arrays.items():
            npz_arrays[f"{case}_probe_{label}"] = array.as_float64()

    total_mismatches = sum(len(r.mismatches) for r in reports.values())
    for case, report in reports.items():
        for m in report.mismatches:
            print(f"MISMATCH {case}: {m}")

    manifest = _build_manifest(evidence, identity, reports, npz_arrays,
                               root, parity)
    fixture_dir = Path(__file__).resolve().parent
    json_path = fixture_dir / "linecorrect_reference.json"
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    npz_path = fixture_dir / "linecorrect_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)  # type: ignore[arg-type]

    print(f"MANIFEST_SHA256 = {_sha256_bytes(json_path.read_bytes())}")
    print(f"NPZ_SHA256 = {_sha256_bytes(npz_path.read_bytes())}")
    print(f"Arrays in NPZ: {len(npz_arrays)}")
    print(f"Total mismatches: {total_mismatches}")
    if total_mismatches:
        raise SystemExit(1)
    print("FIXTURES GENERATED: 30 cases bitwise reconciled")


if __name__ == "__main__":
    main()

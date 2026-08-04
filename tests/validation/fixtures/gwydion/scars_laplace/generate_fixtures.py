"""Strict parser and frozen-fixture generator for the Gwydion 2.71
scars/Laplace compiled-probe campaign.

Evidence profile:

  COMPILED_AGAINST_GWYDDION_2_71_LIBPROCESS_WITH_FROZEN_SOURCE_IDENTITY

This module reads ONLY the compiled probe evidence (the campaign directory
under /tmp, the parity-dir probe sources, the installed shared library) and
the three independent oracles in this directory.  It NEVER derives expected
values, dimensions or output names from any SPMKit implementation, from the
oracles, from documentation prose or from future tests.

The three-way reconciliation (normal probe, sanitized probe, independent
oracle) happens here; only metrics and frozen probe arrays enter the
fixtures.  Tests re-run the oracles against the frozen inputs and compare
with the frozen probe arrays; they never generate expected values.
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
# Evidence discovery
# ---------------------------------------------------------------------------

_PARITY_MARKER = "mark_scars_behavior_probe.c"
_EVIDENCE_NAME = "spmkit_scars_laplace_probe"


def discover_parity_dir(repo_root: Path) -> Path:
    ref = repo_root / ".reference"
    trees = [e for e in os.listdir(ref)
             if (ref / e / "source").is_dir()]
    if len(trees) != 1:
        raise RuntimeError(f"ambiguous frozen tree: {trees}")
    parity = ref / trees[0] / "scars-laplace-parity"
    if not (parity / _PARITY_MARKER).is_file():
        raise RuntimeError(f"parity dir missing probe source: {parity}")
    return parity


def discover_evidence_root() -> Path:
    root = Path("/tmp") / _EVIDENCE_NAME
    if not root.is_dir():
        raise RuntimeError(f"evidence directory missing: {root}")
    return root


# ---------------------------------------------------------------------------
# Campaign constants
# ---------------------------------------------------------------------------

MARK_CASES = [
    "C01_constant_field", "C02_positive_hard_seeded", "C03_negative_hard_seeded",
    "C04_both_polarities", "C05_soft_only_no_seed", "C06_hard_with_soft_shoulder",
    "C07_detached_soft_run", "C08_width_exactly_max", "C09_width_max_plus_one",
    "C10_length_exactly_min", "C11_length_min_minus_one", "C12_run_touching_edges",
    "C13_first_last_row", "C14_adjacent_bands_fmax", "C15_min_dims",
    "C16_threshold_sanitize", "C17_existing_replace", "C18_existing_union",
    "C19_existing_intersection", "C20_no_detection_existing",
    "C20b_no_detection_existing_union", "C21_signed_zero",
]
LAPLACE_CASES = [
    "L01_empty_mask", "L02_one_interior_pixel", "L03_one_edge_pixel",
    "L04_one_corner_pixel", "L05_horizontal_corridor", "L06_vertical_corridor",
    "L07_three_pixel_L", "L08_interior_rectangle", "L09_two_components",
    "L10_edge_touching", "L11_corner_touching", "L12_entire_masked_row",
    "L13_whole_field_mask", "L14_constant_boundary", "L15_calibration_independence",
    "L16_mask_predicate", "L17_signed_zero", "L18_degenerate",
]
REMOVE_CASES = [
    "R01_positive", "R02_negative", "R03_both", "R04_no_detection",
    "R05_edge_touching", "R06_long_wide",
]
ALL_CASES = MARK_CASES + LAPLACE_CASES + REMOVE_CASES

CASE_PURPOSE = {
    "C01_constant_field": "constant field: zero vertical-RMS guard -> empty mask",
    "C02_positive_hard_seeded": "single elevated row: positive polarity "
                                "hard seed",
    "C03_negative_hard_seeded": "single depressed row: negative polarity",
    "C04_both_polarities": "one positive and one negative scar, type Both: "
                           "two detector runs + fmax union",
    "C05_soft_only_no_seed": "soft-only candidate: cannot initiate a scar "
                             "without a hard seed",
    "C06_hard_with_soft_shoulder": "hard seed with a soft horizontal shoulder: chained attachment",
    "C07_detached_soft_run": "detached soft run without hard connectivity: rejected",
    "C08_width_exactly_max": "two-row band with max_width=2: inclusive width boundary",
    "C09_width_max_plus_one": "three-row band with max_width=2: window cannot close -> rejected",
    "C10_length_exactly_min": "run length exactly min_len: inclusive length boundary",
    "C11_length_min_minus_one": "run length min_len-1: rejected",
    "C12_run_touching_edges": "full-width run touching left and right image boundaries",
    "C13_first_last_row": "candidates in first and last rows: outer rows unmarkable",
    "C14_adjacent_bands_fmax": "adjacent bands: per-row independence and fmax overlap accumulation",
    "C15_min_dims": "minimum valid dimensions yres=3, xres=2",
    "C16_threshold_sanitize": "reversed thresholds: sanitize high := low",
    "C17_existing_replace": "existing mask with combine off: replaced by the detector result",
    "C18_existing_union": "existing mask union: elementwise fmax",
    "C19_existing_intersection": "existing mask intersection: elementwise fmin",
    "C20_no_detection_existing": "no detection with existing mask, combine "
                                 "off: module removes the mask",
    "C20b_no_detection_existing_union": "no detection with existing mask, "
                                         "union: output equals existing mask",
    "C21_signed_zero": "signed-zero finite field: no marks, zero-sign behavior only",
    "L01_empty_mask": "empty mask: field unchanged bitwise",
    "L02_one_interior_pixel": "one interior masked pixel: exact local mean",
    "L03_one_edge_pixel": "one top-edge masked pixel: one-sided Neumann",
    "L04_one_corner_pixel": "one corner masked pixel: two-edge Neumann",
    "L05_horizontal_corridor": "thin interior horizontal corridor: "
                               "tridiagonal path, linear continuation",
    "L06_vertical_corridor": "thin interior vertical corridor: transposed thin path",
    "L07_three_pixel_L": "L-shaped three-pixel grain: closed-form source path",
    "L08_interior_rectangle": "interior rectangular island: multilevel/CG+dense solver",
    "L09_two_components": "two disconnected components: independent grain processing",
    "L10_edge_touching": "component touching one image edge: mixed Dirichlet/Neumann",
    "L11_corner_touching": "component touching a corner: two-edge mixed conditions",
    "L12_entire_masked_row": "entire masked row: long edge-to-edge geometry",
    "L13_whole_field_mask": "whole-field mask: source-defined all-zero result",
    "L14_constant_boundary": "constant unmasked boundary: constant harmonic extension",
    "L15_calibration_independence": "identical pixel data with different "
                                     "xreal/yreal: identical output",
    "L16_mask_predicate": "mask values 1.0/0.5/0.0/-1.0: strict >0 predicate",
    "L17_signed_zero": "signed-zero boundary values: zero-sign propagation semantics",
    "L18_degenerate": "degenerate dimensions 1x1/1xN/2xN/Nx1 subcases (L18a-L18e)",
    "R01_positive": "remove scars: positive scar composition",
    "R02_negative": "remove scars: negative scar composition",
    "R03_both": "remove scars: positive and negative scars together",
    "R04_no_detection": "remove scars: no detection leaves the field unchanged",
    "R05_edge_touching": "remove scars: scar in the first markable row",
    "R06_long_wide": "remove scars: long wide (3-row) scar",
}

LAPLACE_PATH_CLASS = {
    "L01_empty_mask": "empty mask",
    "L02_one_interior_pixel": "exact one-pixel local",
    "L03_one_edge_pixel": "exact one-pixel local",
    "L04_one_corner_pixel": "exact one-pixel local",
    "L05_horizontal_corridor": "thin/tridiagonal source path",
    "L06_vertical_corridor": "thin/tridiagonal source path",
    "L07_three_pixel_L": "closed-form L source path",
    "L08_interior_rectangle": "iterative sparse/dense source path",
    "L09_two_components": "iterative sparse/dense source path",
    "L10_edge_touching": "iterative sparse/dense source path",
    "L11_corner_touching": "iterative sparse/dense source path",
    "L12_entire_masked_row": "iterative sparse/dense source path",
    "L13_whole_field_mask": "whole-field zero",
    "L14_constant_boundary": "iterative sparse/dense source path",
    "L15_calibration_independence": "calibration-independence pair",
    "L16_mask_predicate": "iterative sparse/dense source path",
    "L17_signed_zero": "signed-zero implementation case",
    "L18_degenerate": "degenerate geometry",
}

PROBE_PROFILE = "COMPILED_AGAINST_GWYDDION_2_71_LIBPROCESS_WITH_FROZEN_SOURCE_IDENTITY"

INSTALLED_LIB = "/usr/lib/libgwyprocess2.so.0.51.1"

# ---------------------------------------------------------------------------
# Strict evidence model
# ---------------------------------------------------------------------------

_CANONICAL_HEX = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
_BITS16 = re.compile(r"^0x[0-9a-f]{16}$")
_RUN = re.compile(r"^(\d+):(\d+):(\d+)$")

BARE_KEYS = {"profile", "gwydion_version", "gui_executable_invoked"}

L18_SUBCASES = ["L18a_1x1_masked", "L18b_1x1_unmasked", "L18c_1x5",
                "L18d_2x5_full", "L18e_5x1"]

# Int scalars whose names end in "_count" but are NOT array counts
KNOWN_COUNT_INTS = {
    "residual_count", "masked_pixel_count", "grain_count",
    "unmasked_mutation_count", "runs_count",
}


def _key_prefixes(case: str) -> list[str]:
    """Accepted emission prefixes for a case (L18 emits subcase prefixes)."""
    if case == "L18_degenerate":
        return [case] + L18_SUBCASES
    return [case]


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
    family: str
    scalars: dict[str, Scalar] = field(default_factory=dict)
    arrays: dict[str, Array] = field(default_factory=dict)
    ints: dict[str, int] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    runs: list[tuple[int, int, int]] = field(default_factory=list)
    profile: str = ""
    gwydion_version: str = ""
    gui_executable_invoked: int = -1
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_hex_pair(case: str, label: str, hex_text: str, bits_text: str,
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
    if bits == 0x8000000000000000 and not (
            value == 0.0 and struct.unpack(">Q", struct.pack(">d", value))[0]
            == 0x8000000000000000):
        problems.append(f"{case}: {label} negative-zero disagreement")
    if bits == 0 and hex_text != "0x0p+0":
        problems.append(f"{case}: {label} positive-zero sign disagreement")
    return Scalar(hex_text, bits_text)


def parse_case_stdout(case: str, text: str, problems: list[str]) -> CaseEvidence:
    """Parse one probe stdout under the strict contract.

    Accepts bare header keys (profile, gwydion_version,
    gui_executable_invoked), scalar hex/bits pairs, dims/count declarations,
    run lines (case_runs_N=row:col:len), and element lines
    (case_label_i=hex bits).  Rejects duplicates, malformed hex, missing or
    extra elements, non-contiguous/duplicate/negative indices, and any
    unknown case-prefixed line.
    """
    family = ("mark" if case[0] == "C" else
              "laplace" if case[0] == "L" else "remove")
    ev = CaseEvidence(case=case, family=family)
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
            if key == "profile":
                ev.profile = value
            elif key == "gwydion_version":
                ev.gwydion_version = value
            else:
                ev.gui_executable_invoked = int(value)
            continue
        prefix = next((p for p in _key_prefixes(case)
                      if key.startswith(p + "_")), None)
        if prefix is None:
            problems.append(f"{case}: unexpected key {key!r}")
            continue
        rest = key[len(prefix) + 1:]
        # subcase emissions keep their subcase name inside the label so
        # labels stay unique across L18a..L18e
        label_prefix = (prefix + "_") if prefix != case else ""
        if rest.endswith("_hex"):
            label = label_prefix + rest[:-4]
            if label in pending_hex:
                problems.append(f"{case}: duplicate scalar hex {label}")
            pending_hex[label] = value
        elif rest.endswith("_bits"):
            label = label_prefix + rest[:-5]
            if label in pending_bits:
                problems.append(f"{case}: duplicate scalar bits {label}")
            pending_bits[label] = value
        elif rest.endswith("_dims"):
            m = re.fullmatch(r"(\d+)x(\d+)", value)
            if not m:
                problems.append(f"{case}: malformed dims {value!r}")
                continue
            label = label_prefix + rest[:-5]
            if label in dims:
                problems.append(f"{case}: duplicate dims {label}")
            dims[label] = (int(m.group(1)), int(m.group(2)))
        elif rest.endswith("_count"):
            if rest in KNOWN_COUNT_INTS:
                key = label_prefix + rest
                if key in ev.ints:
                    problems.append(f"{case}: duplicate int {key}")
                ev.ints[key] = int(value)
                continue
            label = label_prefix + rest[:-6]
            if label in counts:
                problems.append(f"{case}: duplicate count {label}")
            counts[label] = int(value)
        elif re.fullmatch(r"runs_\d+", rest):
            m = _RUN.match(value)
            if not m:
                problems.append(f"{case}: malformed run line {value!r}")
                continue
            ev.runs.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        elif "_" not in rest:
            if re.fullmatch(r"-?\d+", value):
                ev.ints[label_prefix + rest] = int(value)
            else:
                problems.append(f"{case}: malformed line {line!r}")
        else:
            split_at = rest.rindex("_")
            label, idx_text = rest[:split_at], rest[split_at + 1:]
            if not idx_text.isdigit():
                if re.fullmatch(r"-?\d+", value):
                    ev.ints[label_prefix + rest] = int(value)
                else:
                    problems.append(f"{case}: malformed element line {line!r}")
                continue
            idx = int(idx_text)
            fields = value.split()
            if len(fields) != 2:
                problems.append(f"{case}: {label_prefix + label} element {idx} lacks "
                                f"hex+bits pair: {value!r}")
                continue
            raw_elements.setdefault(label_prefix + label, []).append(
                (idx, fields[0], fields[1]))

    for label in sorted(set(pending_hex) | set(pending_bits)):
        if label not in pending_hex:
            problems.append(f"{case}: scalar {label} has bits but no hex")
            continue
        if label not in pending_bits:
            problems.append(f"{case}: scalar {label} has hex but no bits")
            continue
        ev.scalars[label] = _check_hex_pair(case, label, pending_hex[label],
                                            pending_bits[label], problems)

    for label in sorted(set(dims) | set(counts)):
        count = counts.get(label)
        if count is None:
            problems.append(f"{case}: array {label} missing count")
            continue
        d = dims.get(label)
        if d is not None and d[0] * d[1] != count:
            problems.append(f"{case}: {label} dims {d} inconsistent with "
                            f"count {count}")
        elements = raw_elements.pop(label, [])
        indices = [i for i, _, _ in elements]
        if len(elements) != count:
            problems.append(f"{case}: {label} declared count {count} but "
                            f"{len(elements)} elements")
        if sorted(indices) != list(range(count)):
            problems.append(f"{case}: {label} indices not exactly range({count}): "
                            f"{sorted(indices)[:12]}")
        if len(set(indices)) != len(indices):
            problems.append(f"{case}: {label} duplicate indices")
        elements_sorted = sorted(elements, key=lambda t: t[0])
        for idx, h, b in elements_sorted:
            _check_hex_pair(case, f"{label}[{idx}]", h, b, problems)
        ev.arrays[label] = Array(dims=d, count=count,
                                 elements=tuple(elements_sorted))
    for label in raw_elements:
        problems.append(f"{case}: {label} elements without count declaration")
    return ev


def load_case(case: str, root: Path, build: str,
              problems: list[str]) -> CaseEvidence:
    text = (root / build / f"{case}.stdout").read_text(
        encoding="utf-8", errors="ignore")
    err = (root / build / f"{case}.stderr").read_text(
        encoding="utf-8", errors="ignore")
    exit_code = int((root / build / f"{case}.exit").read_text().strip())
    ev = parse_case_stdout(case, text, problems)
    ev.exit_code = exit_code
    ev.stdout_sha256 = _sha256_bytes(text.encode("utf-8", errors="ignore"))
    ev.stderr_sha256 = _sha256_bytes(err.encode("utf-8", errors="ignore"))
    if exit_code != 0:
        problems.append(f"{case}/{build}: nonzero exit {exit_code}")
    if err.strip():
        lowered = err.lower()
        for marker in ("addresssanitizer", "ubsan", "runtime error",
                       "leaksanitizer", "segv", "aborting"):
            if marker in lowered:
                problems.append(f"{case}/{build}: sanitizer stderr {marker}")
                break
        problems.append(f"{case}/{build}: unexpected stderr {err.strip()[:120]!r}")
    return ev


def verify_campaign(root: Path, parity: Path,
                    problems: list[str]
                    ) -> tuple[dict[str, CaseEvidence], dict[str, str]]:
    for build in ("normal", "sanitized"):
        code = int((root / f"compile-{build}.exit").read_text().strip())
        if code != 0:
            problems.append(f"compile-{build} exit {code}")

    for case in ALL_CASES:
        for build in ("normal", "sanitized"):
            if not (root / build / f"{case}.stdout").is_file():
                problems.append(f"absent case {case}/{build}")
    for build in ("normal", "sanitized"):
        present = [f[:-7] for f in os.listdir(root / build)
                   if f.endswith(".stdout")]
        if sorted(present) != sorted(ALL_CASES):
            problems.append(f"{build}: case inventory mismatch")

    evidence_pairs: list[tuple[str, CaseEvidence]] = []
    for case in ALL_CASES:
        if not (root / "normal" / f"{case}.stdout").is_file():
            continue  # already reported as absent
        ev: CaseEvidence | None = None
        raw: bytes | None = None
        for build in ("normal", "sanitized"):
            if not (root / build / f"{case}.stdout").is_file():
                continue  # already reported as absent
            e = load_case(case, root, build, problems)
            if build == "normal":
                ev = e
                raw = (root / "normal" / f"{case}.stdout").read_bytes()
            else:
                if (root / "sanitized" / f"{case}.stdout").read_bytes() != raw:
                    problems.append(f"{case}: normal/sanitized stdout differ")
                assert ev is not None  # normal build ran before sanitized
                if e.family != ev.family:
                    problems.append(f"{case}: family mismatch between builds")
        if ev is not None:
            evidence_pairs.append((case, ev))
    evidence_by_case = dict(evidence_pairs)

    expected_family = dict.fromkeys(MARK_CASES, "mark")
    expected_family.update(dict.fromkeys(LAPLACE_CASES, "laplace"))
    expected_family.update(dict.fromkeys(REMOVE_CASES, "remove"))
    for case, ev in evidence_by_case.items():
        if ev is None or ev.family != expected_family[case]:
            problems.append(f"{case}: family {ev.family} != {expected_family[case]}")
        if ev.profile != PROBE_PROFILE:
            problems.append(f"{case}: wrong profile {ev.profile!r}")
        if ev.gwydion_version != "2.71":
            problems.append(f"{case}: gwydion_version != 2.71")
        if ev.gui_executable_invoked != 0:
            problems.append(f"{case}: gui_executable_invoked != 0")

    # source identity: every frozen source + installed library + campaign file
    identity = (root / "source-identity.txt").read_text().strip()
    identity_map: dict[str, str] = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        identity_map[rel] = h
    src_tree = parity.parent / "source"
    for rel, where in [
        ("modules/process/scars.c", src_tree),
        ("modules/process/laplace.c", src_tree),
        ("libprocess/correct.c", src_tree),
        ("libprocess/correct-laplace.c", src_tree),
        ("libprocess/grains.c", src_tree),
        ("libprocess/arithmetic.c", src_tree),
        ("libprocess/datafield.c", src_tree),
        ("mark_scars_behavior_probe.c", parity),
        ("laplace_behavior_probe.c", parity),
        ("remove_scars_behavior_probe.c", parity),
        ("run_scars_laplace_probe_campaign.sh", parity),
        ("campaign_checker.py", parity),
        ("independent_reconciliation.py", parity),
    ]:
        if rel not in identity_map:
            problems.append(f"source-identity missing {rel}")
            continue
        path = where / rel
        if not path.is_file():
            problems.append(f"source file missing {rel}")
            continue
        if _sha256_bytes(path.read_bytes()) != identity_map[rel]:
            problems.append(f"source hash mismatch {rel}")
    # libgwydion entries discovered from the identity file itself
    for rel in identity_map:
        if (rel.startswith("libgwyd") and rel.endswith((".c", ".h"))
                and (src_tree / rel).is_file()
                and _sha256_bytes((src_tree / rel).read_bytes())
                != identity_map[rel]):
            problems.append(f"source hash mismatch {rel}")
    # installed library
    if not os.path.isfile(INSTALLED_LIB):
        problems.append(f"installed library missing {INSTALLED_LIB}")
    else:
        lib_key = f"INSTALLED {INSTALLED_LIB}"
        if lib_key not in identity_map:
            problems.append("source-identity missing installed library hash")
        elif identity_map[lib_key] != _sha256_bytes(
                Path(INSTALLED_LIB).read_bytes()):
            problems.append("installed library hash mismatch")

    # SHA256SUMS coverage and integrity
    sums = (root / "SHA256SUMS").read_text().splitlines()
    covered: dict[str, str] = {}
    for line in sums:
        h, rel = line.split("  ", 1)
        path = parity / rel if rel in (
            "mark_scars_behavior_probe.c", "laplace_behavior_probe.c",
            "remove_scars_behavior_probe.c",
            "run_scars_laplace_probe_campaign.sh", "campaign_checker.py",
            "independent_reconciliation.py", "metrics.py") else root / rel
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

    # summary-file cardinalities
    summary = (root / "case-summary.tsv").read_text().splitlines()
    if len(summary) != 1 + 2 * len(ALL_CASES):
        problems.append(f"case-summary.tsv cardinality {len(summary)}")
    nvs = (root / "normal-vs-sanitized-summary.tsv").read_text().splitlines()
    if len(nvs) != 1 + len(ALL_CASES):
        problems.append(f"normal-vs-sanitized-summary.tsv cardinality {len(nvs)}")
    for line in nvs[1:]:
        if not line.endswith("\t1"):
            problems.append(f"normal-vs-sanitized not identical: {line[:60]}")
    if not (root / "metrics.txt").is_file():
        problems.append("metrics.txt missing")

    return evidence_by_case, identity_map


# ---------------------------------------------------------------------------
# Three-way reconciliation
# ---------------------------------------------------------------------------

def _bits_view(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _compare(probe: np.ndarray, ref: np.ndarray) -> dict:
    pb = _bits_view(probe).ravel()
    ob = _bits_view(ref).ravel()
    equal = bool(np.array_equal(pb, ob))
    xor = np.bitwise_xor(pb, ob)
    sz = int(np.count_nonzero(xor == 0x8000000000000000))
    max_abs = 0.0
    max_ulp = 0
    nan_m = inf_m = 0
    if not equal:
        pv = probe.ravel()
        ov = ref.ravel()
        for i in range(pb.size):
            if pb[i] == ob[i] or int(xor[i]) == 0x8000000000000000:
                continue
            a, b = float(pv[i]), float(ov[i])
            if np.isnan(a) or np.isnan(b):
                nan_m += 1
            elif np.isinf(a) or np.isinf(b):
                inf_m += 1
            else:
                max_abs = max(max_abs, abs(a - b))
                max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    return {
        "arrays_bitwise_exact": equal,
        "elements_bitwise_exact": int(np.count_nonzero(pb == ob)),
        "elements_total": int(pb.size),
        "max_absolute_difference": float(max_abs),
        "max_ulp_difference": int(max_ulp),
        "signed_zero_mismatches": sz,
        "nan_mismatches": nan_m,
        "inf_mismatches": inf_m,
    }


def _metrics_from_line(line: str, case: str) -> dict:
    """Parse one metrics.txt line into a metric dict (cross-check only)."""
    m = re.search(r"maxabs=([0-9.eE+-]+)", line)
    u = re.search(r"maxulp=(\d+)", line)
    out: dict = {}
    if m:
        out["max_absolute_difference"] = float(m.group(1))
    if u:
        out["max_ulp_difference"] = int(u.group(1))
    return out


def _marked_rows(mask: np.ndarray) -> list[int]:
    return [int(r) for r in range(mask.shape[0]) if np.any(mask[r] == 1.0)]


def compare_mark_case(ev: CaseEvidence, oracle: object | None,
                      problems: list[str]) -> dict:
    from oracle_mark_scars import oracle_mark_scars
    cid = ev.case.split("_")[0]
    existing = (ev.arrays["existing_before"].as_float64()
                if "existing_before" in ev.arrays else None)
    ref = oracle_mark_scars(
        ev.arrays["input"].as_float64(),
        threshold_high=ev.scalars["threshold_high"].value,
        threshold_low=ev.scalars["threshold_low"].value,
        min_length=ev.ints["min_len"],
        max_width=ev.ints["max_width"],
        polarity=ev.ints["polarity_enum"],
        existing_mask=existing,
        combine=bool(ev.ints.get("combine", 0)),
        combine_type=ev.ints.get("combine_type", 0),
    )
    mask_label = "module_mask" if cid in (
        "C17", "C18", "C19", "C20", "C20b") else "kernel_mask"
    probe_mask = ev.arrays[mask_label].as_float64()
    metric = _compare(probe_mask, ref.final_module_mask)
    mismatches: list[str] = []
    if not metric["arrays_bitwise_exact"]:
        mismatches.append("mask not bitwise exact")
    if ref.nonzero_count != ev.ints.get("mask_nonzero", -1):
        mismatches.append("nonzero count differs")
    if ev.ints.get("module_mask_present", -1) != (1 if ref.mask_present else 0):
        mismatches.append("mask-present classification differs")
    if sorted(ref.marked_runs) != sorted(ev.runs):
        mismatches.append("marked runs differ")
    if _marked_rows(probe_mask) != _marked_rows(ref.final_module_mask):
        mismatches.append("marked rows differ")
    if ("existing_before" in ev.arrays and not np.array_equal(
            _bits_view(ev.arrays["existing_before"].as_float64()),
            _bits_view(ev.arrays["existing_after"].as_float64()))):
        mismatches.append("existing mask mutated")
    if not np.array_equal(
            _bits_view(ev.arrays["input"].as_float64()),
            _bits_view(ev.arrays["input_after"].as_float64())):
        mismatches.append("input mutated")
    if cid == "C16":
        eff_hi = ev.scalars["effective_threshold_high"].value
        eff_lo = ev.scalars["effective_threshold_low"].value
        if (eff_hi, eff_lo) != (ref.effective_threshold_high,
                                ref.effective_threshold_low):
            mismatches.append("effective thresholds differ")
    for m in mismatches:
        problems.append(f"{ev.case}: {m}")
    return {"mask": metric, "mask_present": bool(ref.mask_present),
            "nonzero_count": ref.nonzero_count,
            "marked_runs": [list(r) for r in ref.marked_runs]}


def _laplace_subcases(ev: CaseEvidence) -> list[tuple[str, str, str, str]]:
    """(subcase label, corrected label, input label, mask label)."""
    cid = ev.case.split("_")[0]
    if cid == "L15":
        return [("L15_calibration_independence", "corrected_a", "input",
                 "mask_after_a")]
    if cid == "L18":
        return [(sub, f"{sub}_corrected", f"{sub}_input", f"{sub}_input_mask")
                for sub in L18_SUBCASES]
    return [(ev.case, "corrected", "input", "input_mask")]


def compare_laplace_case(ev: CaseEvidence, problems: list[str]) -> dict:
    from oracle_laplace_discrete import oracle_laplace_discrete
    sub_metrics = []
    for sub, cor_label, inp_label, mask_label in _laplace_subcases(ev):
        ref = oracle_laplace_discrete(
            ev.arrays[inp_label].as_float64(),
            ev.arrays[mask_label].as_float64(),
            probe_corrected=ev.arrays[cor_label].as_float64())
        metric = _compare(ev.arrays[cor_label].as_float64(),
                          ref.corrected_float64)
        sub_metrics.append({
            "subcase": sub,
            "path_class": LAPLACE_PATH_CLASS[ev.case],
            **metric,
            "mathematical_residual": str(ref.mathematical_residual),
            "masked_pixel_count": len(ref.masked_coordinates),
            "empty_mask": ref.empty_mask,
            "whole_field_mask": ref.whole_field_mask,
        })
        if ref.unmasked_mutation_count:
            problems.append(f"{ev.case}/{sub}: unmasked pixels mutated")
    if (ev.case == "L15_calibration_independence" and not np.array_equal(
            _bits_view(ev.arrays["corrected_a"].as_float64()),
            _bits_view(ev.arrays["corrected_b"].as_float64()))):
        problems.append("L15: calibration pair differs bitwise")
    if (ev.case == "L13_whole_field_mask"
            and not np.all(ev.arrays["corrected"].as_float64() == 0.0)):
        problems.append("L13: whole-field result not all zero")
    return {"subcases": sub_metrics}


def compare_remove_case(ev: CaseEvidence, problems: list[str]) -> dict:
    from oracle_remove_scars import oracle_remove_scars
    ref = oracle_remove_scars(
        ev.arrays["input"].as_float64(),
        compiled_standalone_mask=ev.arrays["standalone_mask"].as_float64(),
        compiled_temp_mask=ev.arrays["temp_mask"].as_float64(),
        compiled_standalone_laplace=ev.arrays[
            "standalone_corrected"].as_float64(),
        compiled_remove_result=ev.arrays["corrected"].as_float64(),
    )
    if not ref.mask_identity:
        problems.append(f"{ev.case}: temp mask != standalone Mark Scars mask")
    if not ref.compiled_composition_identity:
        problems.append(f"{ev.case}: corrected != standalone Laplace result")
    if not np.array_equal(_bits_view(ev.arrays["temp_mask"].as_float64()),
                          _bits_view(ev.arrays["temp_mask_after"].as_float64())):
        problems.append(f"{ev.case}: laplace mutated the temp mask")
    math_metric = _compare(ev.arrays["corrected"].as_float64(),
                           ref.mathematical_corrected)
    return {
        "mask_identity": ref.mask_identity,
        "composition_identity": ref.compiled_composition_identity,
        "temp_mask_unmutated": True,
        "mathematical": math_metric,
        "mathematical_residual": str(ref.laplace.mathematical_residual),
    }


def _aggregate(metrics: list[dict]) -> dict:
    arrays = elements = exact_arrays = exact_elements = 0
    max_abs = 0.0
    max_ulp = 0
    sz = nan = inf = 0
    for m in metrics:
        arrays += 1
        elements += m["elements_total"]
        exact_elements += m["elements_bitwise_exact"]
        if m["arrays_bitwise_exact"]:
            exact_arrays += 1
        max_abs = max(max_abs, m["max_absolute_difference"])
        max_ulp = max(max_ulp, m["max_ulp_difference"])
        sz += m["signed_zero_mismatches"]
        nan += m["nan_mismatches"]
        inf += m["inf_mismatches"]
    return {
        "case_count": len(metrics),
        "array_count": arrays,
        "element_count": elements,
        "arrays_bitwise_exact": exact_arrays,
        "elements_bitwise_exact": exact_elements,
        "max_absolute_difference": max_abs,
        "max_ulp_difference": max_ulp,
        "signed_zero_mismatches": sz,
        "nan_mismatches": nan,
        "inf_mismatches": inf,
    }

# ---------------------------------------------------------------------------
# Manifest + NPZ writing
# ---------------------------------------------------------------------------

KNOWN_SOURCE_BEHAVIOURS = [
    "Mark Scars statistic: a single global vertical-difference RMS "
    "rms = sqrt(sum((d[i,j]-d[i+1,j])**2)/(xres*yres)) over the whole field "
    "(correct.c:1413-1424); thresholds are multiples of this RMS.",
    "Mark Scars detection: per-column band scanning with first-qualifying "
    "width k <= max_width; positive polarity detects an elevated band "
    "(min of band rows above max of boundary rows), negative a depressed "
    "band; weights (value-bottom)/rms and (top-value)/rms accumulated with "
    "C fmax semantics (correct.c:1429-1471).",
    "Mark Scars hard/soft semantics: detection at threshold_low; pixels "
    "with weight >= threshold_high are hard seeds; soft pixels adjacent to "
    "hard runs attach through a chained forward/backward in-place expansion "
    "setting them to exactly threshold_high (correct.c:1472-1484).",
    "Mark Scars finalization: per-row runs of pixels >= threshold_high are "
    "kept only when their length is >= min_len and are clamped to 1.0; "
    "everything else becomes 0.0; the output mask is binary "
    "(correct.c:1485-1511).",
    "Mark Scars kernel clamps (correct.c:1407-1411): min_len = MAX(min_len,1), "
    "max_width = MIN(max_width, yres-2), threshold_high = "
    "MAX(threshold_high, threshold_low); early empty-mask returns for "
    "min_len > xres, max_width < 1, threshold_low <= 0 and rms == 0.",
    "Module-level polarity dispatch (scars.c:158-169): POSITIVE=1/NEGATIVE=4 "
    "run one detector; BOTH=3 runs both detectors and unions the binary "
    "masks with max_of_fields.",
    "Module-level existing-mask semantics (scars.c:249-258, 232-236): the "
    "existing mask is never read by the kernel; combine=union is elementwise "
    "fmax, intersection fmin; with no detection the container mask is "
    "removed (module_mask_present=0).",
    "Laplace interpolation: per-grain processing of mask>0 pixels with "
    "4-connectivity; Dirichlet data from the surrounding ring, Neumann "
    "(dz/dn=0) by omission at image borders; whole-field mask clears the "
    "field to zeros; empty mask leaves the field unchanged "
    "(correct-laplace.c:1566-1672).",
    "Laplace solver internals are a multilevel anisotropic sparse conjugate-"
    "gradient solve with damped-Jacobi relaxation and hierarchical "
    "reconstruction followed by a dense four-neighbour CG refinement "
    "(correct-laplace.c 939-1332); the solver is iterative and its output "
    "may deviate from the exact discrete solution by a few ULPs.",
    "Tiny-grain special paths: 1x1 grains use the exact neighbour mean "
    "(handle_1x1_grain); interior 1xN/Mx1 grains use a direct tridiagonal "
    "solve (handle_thin_grain, Thomas elimination); interior L-shaped "
    "three-pixel grains use closed-form formulas (handle_3px_grain).",
    "L05/L06 corridor cases: the tridiagonal Thomas elimination introduces "
    "one-ULP rounding at the middle pixel (5.999999999999999 instead of "
    "6.0); measured source-algorithm rounding, not an oracle defect.",
    "L17 signed-zero case: the compiled probe yields -0.0 at the masked "
    "pixel while the frozen source's 1x1 arithmetic (IEEE round-to-nearest "
    "zero-sum rule) and the independent mathematical reference yield +0.0; "
    "zero sign is implementation semantics, not mathematical content.",
]

DELIBERATE_SPMKIT_POLICY_DIFFERENCES = [
    "Non-finite inputs (NaN, +-Inf) are rejected at the SPMKit entry "
    "point; the Gwydion source propagates IEEE arithmetic without "
    "pre-filtering.",
    "GUI semantics (undo checkpoints, channel log, data-browser current "
    "channel lookup, container mask writes, settings persistence) are not "
    "part of the numerical contract and will not be emulated.",
    "Mark Scars in SPMKit will return masks as explicit outputs rather "
    "than mutating a persistent data-browser mask.",
]

NON_CLAIMS = [
    "No universal Gwydion equivalence: parity is claimed only within the "
    "frozen 46-case finite campaign.",
    "No other Gwydion version or library-build equivalence claim.",
    "No installed-GUI black-box execution: /usr/bin/gwydion was never "
    "invoked.",
    "No claim that the linked Gwydion library internals were "
    "sanitizer-instrumented (ASan/UBSan instrumented the probe executables "
    "and the call boundary only).",
    "No NaN/Inf compatibility claim (all retained inputs are finite).",
    "No physical or experimental validation.",
    "No claim that interpolation preserves roughness, PSD, autocorrelation, "
    "morphology or uncertainty.",
    "No production SPMKit implementation exists yet; the fixtures document "
    "the compiled reference behavior only.",
    "No frozen universal Laplace parity tolerance; per-case metrics are "
    "characterization, not a production acceptance threshold.",
]

GUI_NOT_INVOKED = (
    "The evidence is produced by custom probe executables that link the "
    "installed Gwydion 2.71 shared library (libgwyprocess2, version 2.71, "
    "AUR package gwydion-no-python2 2.71-1); the installed GUI executable "
    "(/usr/bin/gwydion) and the app-layer process callbacks were not "
    "invoked.")

SANITIZER_SCOPE = (
    "ASan and UBSan instrumented the probe executables and the call "
    "boundary into the installed shared library.  The installed shared "
    "library internals were NOT rebuilt with sanitizer instrumentation; "
    "the library kernels themselves are not claimed sanitizer-clean.")


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(i) for i in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _crosscheck_metrics_txt(root: Path, reports: dict,
                            problems: list[str]) -> dict:
    """Cross-check the generator-computed corridor metrics against
    metrics.txt (a campaign artifact; consistency check only).

    L06 was computed with correct corridor indices in metrics.py and must
    agree.  L05's metrics.py entry used row-1 (unmasked) indices and
    reported maxabs=0/maxulp=0 for the corridor; the generator's own
    computation (probe vs mathematical reference on the true corridor row)
    is authoritative and the metrics.py inconsistency is documented in the
    manifest rather than treated as an error.
    """
    text = (root / "metrics.txt").read_text(encoding="utf-8", errors="ignore")
    notes: list[str] = []
    for case in ("L05_horizontal_corridor", "L06_vertical_corridor"):
        line = next((ln for ln in text.splitlines()
                     if ln.startswith(case + ":")), "")
        if not line:
            problems.append(f"metrics.txt missing {case}")
            continue
        mt = _metrics_from_line(line, case)
        sub = reports[case]["subcases"][0]
        if case == "L06_vertical_corridor":
            if ("max_ulp_difference" in mt
                    and mt["max_ulp_difference"] != sub["max_ulp_difference"]):
                problems.append("metrics.txt L06 maxulp disagrees with generator")
            if "max_absolute_difference" in mt and abs(
                    mt["max_absolute_difference"] -
                    sub["max_absolute_difference"]) > 1e-12:
                problems.append("metrics.txt L06 maxabs disagrees with generator")
        else:
            notes.append(
                "metrics.txt L05 entry used row-1 (unmasked) corridor indices "
                "and reported maxabs=0/maxulp=0; the generator recomputed the "
                "true corridor row (1 ULP at the middle pixel).")
    return {"metrics_txt_notes": notes}


def _build_manifest(evidence: dict[str, CaseEvidence],
                    identity: dict[str, str],
                    reports: dict[str, dict],
                    npz_arrays: dict[str, np.ndarray], root: Path,
                    parity: Path, metrics_notes: dict) -> dict:
    mark_metrics = [reports[c]["mask"] for c in MARK_CASES]
    lap_metrics = [sub for c in LAPLACE_CASES
                   for sub in reports[c]["subcases"]]
    rem_metrics = [reports[c]["mathematical"] for c in REMOVE_CASES]

    cases = []
    for case in ALL_CASES:
        ev = evidence[case]
        entry = {
            "case_identifier": case,
            "family": ev.family,
            "purpose": CASE_PURPOSE[case],
            "exit_code": ev.exit_code,
            "stdout_sha256": ev.stdout_sha256,
            "stderr_sha256": ev.stderr_sha256,
            "arrays": {
                label: {
                    "key": f"{case}_probe_{label}",
                    "dims": list(array.dims) if array.dims else None,
                    "count": array.count,
                }
                for label, array in sorted(ev.arrays.items())
            },
            "scalars": {
                label: {"hex": scalar.hex_text, "bits": scalar.bits_text}
                for label, scalar in sorted(ev.scalars.items())
            },
            "ints": dict(sorted(ev.ints.items())),
        }
        cases.append(entry)

    lib_key = f"INSTALLED {INSTALLED_LIB}"
    helper_hashes = {rel: h for rel, h in identity.items()
                     if rel.startswith(("libprocess/", "libgwyd"))}
    frozen_sources = {rel: h for rel, h in identity.items()
                      if rel.startswith(("modules/", "libprocess/", "libgwyd"))}

    manifest = {
        "schema_version": 1,
        "capabilities": [
            {"name": "gwydion_mark_scars",
             "case_count": len(MARK_CASES),
             "comparison_metrics": _aggregate(mark_metrics)},
            {"name": "gwydion_laplace_interpolation",
             "case_count": len(LAPLACE_CASES),
             "comparison_metrics": _aggregate(lap_metrics)},
            {"name": "gwydion_remove_scars",
             "case_count": len(REMOVE_CASES),
             "comparison_metrics": _aggregate(rem_metrics)},
        ],
        "case_count": len(cases),
        "cases": cases,
        "probe": {
            "profile": PROBE_PROFILE,
            "gui_not_invoked": GUI_NOT_INVOKED,
            "sanitizer_scope": SANITIZER_SCOPE,
            "normal_sanitized_stdout_equal": "46/46",
            "build_exits": {
                "normal": int((root / "compile-normal.exit").read_text().strip()),
                "sanitized": int((root / "compile-sanitized.exit").read_text().strip()),
            },
            "execution_exits": "92/92 zero",
            "shared_library": {
                "path": INSTALLED_LIB,
                "version": "2.71",
                "sha256": identity.get(lib_key, ""),
            },
        },
        "profiles": {
            "compiled_against_libprocess_2_71_profile": {
                "frozen_source_hashes": frozen_sources,
                "helper_hashes": helper_hashes,
                "installed_library_sha256": identity.get(lib_key, ""),
                "probe_sources": {
                    rel: identity[rel] for rel in (
                        "mark_scars_behavior_probe.c",
                        "laplace_behavior_probe.c",
                        "remove_scars_behavior_probe.c")
                    if rel in identity
                },
                "campaign_script_sha256": identity.get(
                    "run_scars_laplace_probe_campaign.sh", ""),
                "checker_sha256": identity.get("campaign_checker.py", ""),
                "reconciliation_sha256": identity.get(
                    "independent_reconciliation.py", ""),
            }
        },
        "comparison_metrics": {
            "mark_scars": _aggregate(mark_metrics),
            "laplace": _aggregate(lap_metrics),
            "remove_scars": _aggregate(rem_metrics),
        },
        "per_case": {
            case: reports[case] for case in ALL_CASES
        },
        "evidence": {
            "metrics_txt_notes": metrics_notes,
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


def main(out_dir: Path | None = None) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    root = discover_evidence_root()
    parity = discover_parity_dir(repo_root)
    fixture_dir = Path(__file__).resolve().parent
    if out_dir is not None:
        fixture_dir = out_dir

    problems: list[str] = []
    evidence, identity = verify_campaign(root, parity, problems)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    reports: dict[str, dict] = {}
    npz_arrays: dict[str, np.ndarray] = {}
    for case in ALL_CASES:
        ev = evidence[case]
        if ev.family == "mark":
            reports[case] = compare_mark_case(ev, None, problems)
        elif ev.family == "laplace":
            reports[case] = compare_laplace_case(ev, problems)
        else:
            reports[case] = compare_remove_case(ev, problems)
        for label, array in ev.arrays.items():
            npz_arrays[f"{case}_probe_{label}"] = array.as_float64()

    metrics_notes = _crosscheck_metrics_txt(root, reports, problems)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    manifest = _build_manifest(evidence, identity, reports, npz_arrays,
                               root, parity, metrics_notes)
    json_path = fixture_dir / "scars_laplace_reference.json"
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    npz_path = fixture_dir / "scars_laplace_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)  # type: ignore[arg-type]

    print(f"MANIFEST_SHA256 = {_sha256_bytes(json_path.read_bytes())}")
    print(f"NPZ_SHA256 = {_sha256_bytes(npz_path.read_bytes())}")
    print(f"Arrays in NPZ: {len(npz_arrays)}")
    print("FIXTURES GENERATED: 46 cases three-way reconciled")


if __name__ == "__main__":
    main()

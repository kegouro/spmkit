"""Strict parser and frozen-fixture generator for the Gwydion 2.71
neighborhood-filters compiled-probe campaign (Rank Filter, disc Median,
Gaussian).

Evidence profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION

Compiled expected arrays derive exclusively from the compiled probe
evidence; the oracles are reconciliation layers only and never replace
compiled outputs.

Case model (71 logical cases, 71 physical executions per build):

  * R01-R20  : Rank Filter (PUBLIC_TOOL_DOMAIN_CASE; R18/R19/R20 also
               OUTPUT_MODE_CASE);
  * M01-M18, M20: disc Median (PUBLIC_TOOL_DOMAIN_CASE);
  * G01-G20  : Gaussian (G05 is LIBRARY_DOMAIN_ONLY_CASE for sigma=0; the
               rest are PUBLIC_TOOL_DOMAIN_CASE);
  * X01-X05  : CROSS_OPERATION_RELATION_CASE (relations, not canonical);
  * X06      : DETERMINISM_WITNESS (in-process replay pairs);
  * F01-F06  : FOOTPRINT_RELATION_CASE (pure footprint geometry).

Canonical numerical parity cases = the PUBLIC_TOOL_DOMAIN + LIBRARY_DOMAIN
cases whose result arrays are stored: R01-R17+R20 (18), M01-M18+M20 (19),
G01-G20 minus G05? No: G05 stores its no-op result too (19).  Total 56
canonical arrays; X/F/R18/R19 are relation/output-mode evidence stored via
relations in JSON, and replay arrays are stored once.
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
EVIDENCE = Path("/tmp/spmkit_a2_neighborhood_filters_probe")
EVIDENCE2 = Path("/tmp/spmkit_a2_neighborhood_filters_probe_run2")

HEX_RE = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
BITS_RE = re.compile(r"^0x[0-9a-f]{16}$")
INT_RE = re.compile(r"^-?\d+$")

# Percentile map from the frozen probe call sites (case -> (p1, p2, both, diff))
PROBE_PERCENTILES = {
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

# Case purpose map (compact; derived from the retained-case matrix)
PURPOSES = {
    "R01_CONSTANT": "constant field; no-op output",
    "R02_MONOTONIC_SMALL": "small monotonic field; identifiable ranks",
    "R03_PERCENTILE_ZERO": "percentile 0; minimum endpoint dispatch",
    "R04_PERCENTILE_ONE": "percentile 1; maximum endpoint dispatch",
    "R05_PERCENTILE_HALF": "percentile 0.5 rank conversion",
    "R06_PERCENTILE_ROUND_DOWN_EDGE": "percentile just below rank boundary",
    "R07_PERCENTILE_EXACT_BOUNDARY": "exact rank conversion boundary",
    "R08_PERCENTILE_ROUND_UP_EDGE": "percentile just above rank boundary",
    "R09_DUPLICATE_VALUES": "repeated values around the rank",
    "R10_SIGNED_ZERO": "signed-zero ordering",
    "R11_RADIUS_ONE": "smallest public radius",
    "R12_RADIUS_TWO": "footprint geometry change",
    "R13_LARGE_RADIUS_SMALL_FIELD": "radius rivals field dimensions",
    "R14_ONE_BY_ONE": "1x1 input",
    "R15_ONE_BY_N": "single row",
    "R16_N_BY_ONE": "single column",
    "R17_NON_SQUARE": "rectangular field",
    "R18_BOTH_OUTPUTS": "primary and secondary rank outputs",
    "R19_DIFFERENCE_OUTPUT": "difference output mode",
    "R20_INPUT_NON_MUTATION": "both+difference with mutation check",
    "M01_CONSTANT": "constant field",
    "M02_ODD_SIZE_THREE": "3x3 footprint geometry",
    "M03_ODD_SIZE_FIVE": "5x5 footprint geometry",
    "M04_EVEN_SIZE_TWO": "smallest tool size (even footprint)",
    "M05_EVEN_SIZE_FOUR": "even-size centering",
    "M06_UPPER_MEDIAN": "upper-median rank",
    "M07_DUPLICATE_VALUES": "duplicate values",
    "M08_SIGNED_ZERO": "signed-zero ordering",
    "M09_CORNER": "corner border",
    "M10_TOP_EDGE": "top edge border",
    "M11_LEFT_EDGE": "left edge border",
    "M12_BOTTOM_RIGHT_EDGE": "bottom-right edges",
    "M13_SIZE_LARGER_THAN_FIELD": "footprint exceeds field",
    "M14_ONE_BY_ONE": "1x1 field",
    "M15_ONE_BY_N": "one row",
    "M16_N_BY_ONE": "one column",
    "M17_NON_SQUARE": "rectangular field",
    "M18_TOOL_SIZE_MAX": "size 31",
    "M20_INPUT_NON_MUTATION": "mutation check",
    "G01_CONSTANT": "constant preservation",
    "G02_SIGMA_TOOL_MIN": "sigma 0.01",
    "G03_SIGMA_DEFAULT": "sigma 5.0",
    "G04_SIGMA_TOOL_MAX": "sigma 40.0 on small field (cap)",
    "G05_SIGMA_ZERO_LIBRARY": "library-domain sigma=0 no-op",
    "G06_IMPULSE_INTERIOR": "interior impulse",
    "G07_IMPULSE_CORNER": "corner impulse (mirror)",
    "G08_IMPULSE_EDGE": "edge impulse (mirror)",
    "G09_ONE_BY_ONE": "1x1 field",
    "G10_ONE_BY_N": "single row",
    "G11_N_BY_ONE": "single column",
    "G12_NON_SQUARE_WIDE": "wide field cap",
    "G13_NON_SQUARE_TALL": "tall field cap",
    "G14_RESOLUTION_CAP": "kernel much larger than field",
    "G15_ODD_RESOLUTION_FORCING": "cap yields even value (forced odd)",
    "G16_SIGNED_ZERO": "signed-zero transitions",
    "G17_POSITIVE_NEGATIVE_VALUES": "normalization and cancellation",
    "G18_LARGE_DYNAMIC_RANGE": "finite values with extreme magnitudes",
    "G19_HORIZONTAL_INTERMEDIATE": "horizontal first pass",
    "G20_INPUT_NON_MUTATION": "mutation check",
    "X01_CONSTANT_RELATION": "all three operations on a constant field",
    "X02_RANK_ENDPOINTS": "rank percentile 0/1 endpoint dispatch",
    "X03_RANK_HALF_VS_MEDIAN": "rank-half vs median shared footprint",
    "X04_FOOTPRINT_GEOMETRY": "shared side-5 footprint coordinates",
    "X05_SIGNED_ZERO_RELATION": "signed-zero across operations",
    "X06_DETERMINISTIC_REPLAY": "in-process deterministic replay",
    "F01_FOOTPRINT_SIDE3": "footprint geometry side 3",
    "F02_FOOTPRINT_SIDE5": "footprint geometry side 5",
    "F03_FOOTPRINT_SIDE2": "footprint geometry side 2",
    "F04_FOOTPRINT_SIDE4": "footprint geometry side 4",
    "F05_FOOTPRINT_SIDE31": "footprint geometry side 31",
    "F06_FOOTPRINT_SIDE17": "footprint geometry side 17",
}

OUTPUT_MODE_CASES = {"R18_BOTH_OUTPUTS", "R19_DIFFERENCE_OUTPUT",
                     "R20_INPUT_NON_MUTATION"}
CROSS_CASES = {"X01_CONSTANT_RELATION", "X02_RANK_ENDPOINTS",
               "X03_RANK_HALF_VS_MEDIAN", "X04_FOOTPRINT_GEOMETRY",
               "X05_SIGNED_ZERO_RELATION"}
REPLAY_CASE = "X06_DETERMINISTIC_REPLAY"
FOOTPRINT_CASES = {"F01_FOOTPRINT_SIDE3", "F02_FOOTPRINT_SIDE5",
                   "F03_FOOTPRINT_SIDE2", "F04_FOOTPRINT_SIDE4",
                   "F05_FOOTPRINT_SIDE31", "F06_FOOTPRINT_SIDE17"}
LIBRARY_ONLY_CASES = {"G05_SIGMA_ZERO_LIBRARY"}

RANK_CASES = [f"R{i:02d}_" for i in range(1, 21)]
MEDIAN_CASES = ["M01_CONSTANT", "M02_ODD_SIZE_THREE", "M03_ODD_SIZE_FIVE",
                "M04_EVEN_SIZE_TWO", "M05_EVEN_SIZE_FOUR", "M06_UPPER_MEDIAN",
                "M07_DUPLICATE_VALUES", "M08_SIGNED_ZERO", "M09_CORNER",
                "M10_TOP_EDGE", "M11_LEFT_EDGE", "M12_BOTTOM_RIGHT_EDGE",
                "M13_SIZE_LARGER_THAN_FIELD", "M14_ONE_BY_ONE", "M15_ONE_BY_N",
                "M16_N_BY_ONE", "M17_NON_SQUARE", "M18_TOOL_SIZE_MAX",
                "M20_INPUT_NON_MUTATION"]
GAUSSIAN_CASES = [f"G{i:02d}_" for i in range(1, 21)]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


REPO_ROOT = Path(__file__).resolve().parents[5]


def _find_under_reference(rel_parts: tuple[str, ...]) -> Path | None:
    ref = REPO_ROOT / ".reference"
    if not ref.is_dir():
        return None
    for entry in sorted(os.listdir(ref)):
        cand = ref / entry / Path(*rel_parts)
        if cand.is_file():
            return cand
    return None


@dataclass
class CaseEvidence:
    case: str
    execution: str
    classification: str
    operation: str | None
    ints: dict[str, int] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    scalars: dict[str, str] = field(default_factory=dict)   # raw hex+bits
    arrays: dict[str, np.ndarray] = field(default_factory=dict)
    array_bits: dict[str, list[str]] = field(default_factory=dict)
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    purpose: str = ""


def parse_stdout(case: str, text: str, problems: list[str]) -> CaseEvidence:
    # X06 is a relation-only replay witness: its transcript carries
    # per-sub-case keys (X06_..._0_rank_* / X06_..._1_rank_*) whose
    # sub-arrays are replay pairs, not canonical arrays.  Only the
    # top-level header is parsed; replay equality is verified separately.
    if case == REPLAY_CASE:
        ev = CaseEvidence(case=case, execution="", classification="",
                          operation="replay")
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k in ("profile", "gwydion_version", "gui_executable_invoked",
                         "schema_version"):
                    continue
                if k == case + "_xres":
                    ev.ints["xres"] = int(v)
                elif k == case + "_yres":
                    ev.ints["yres"] = int(v)
        return ev
    ev = CaseEvidence(case=case, execution="", classification="", operation=None)
    pending_hex: dict[str, str] = {}
    pending_bits: dict[str, str] = {}
    dims: dict[str, tuple[int, int]] = {}
    counts: dict[str, int] = {}
    raw: dict[str, list[tuple[int, str, str]]] = {}

    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in ("profile", "gwydion_version", "gui_executable_invoked",
                   "schema_version"):
            continue
        if not key.startswith(case + "_"):
            continue
        rest = key[len(case) + 1:]
        if rest.endswith("_hex"):
            pending_hex[rest[:-4]] = value
        elif rest.endswith("_bits"):
            pending_bits[rest[:-5]] = value
        elif rest.endswith("_dims"):
            m = re.fullmatch(r"(\d+)x(\d+)", value)
            if not m:
                problems.append(f"{case}: malformed dims {value!r}")
                continue
            dims[rest[:-5]] = (int(m.group(1)), int(m.group(2)))
        elif rest.endswith("_count"):
            counts[rest[:-6]] = int(value)
        elif re.fullmatch(r"footprint_rowspan_(\d+)_(from|to)", rest):
            ev.ints[rest] = int(value)
        elif rest in ("status", "exit_classification"):
            ev.texts[rest] = value
        elif INT_RE.match(value):
            ev.ints[rest] = int(value)
        else:
            m = re.fullmatch(r"(.*)_(\d+)", rest)
            if m and re.fullmatch(r"-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+ "
                                  r"0x[0-9a-f]{16}", value):
                # array element "hex bits"
                label, idx = m.group(1), int(m.group(2))
                parts = value.split()
                raw.setdefault(label, []).append((idx, parts[0], parts[1]))
            elif re.fullmatch(r"-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+ "
                              r"0x[0-9a-f]{16}", value):
                # scalar emitted as "hex bits" without a suffix (sigma,
                # kernel_sum)
                h, b = value.split()
                actual = struct.unpack(">Q", struct.pack(">d",
                                                         float.fromhex(h)))[0]
                if actual != int(b, 16):
                    problems.append(f"{case}: {rest} hex/bits disagreement")
                if float.fromhex(h) == 0.0:
                    want = 0x8000000000000000 if h.startswith("-") else 0
                    if int(b, 16) != want:
                        problems.append(f"{case}: {rest} signed-zero mismatch")
                ev.scalars[rest] = h
            else:
                problems.append(f"{case}: malformed line {line!r}")

    for label in sorted(set(pending_hex) | set(pending_bits)):
        if label not in pending_hex or label not in pending_bits:
            problems.append(f"{case}: scalar {label} missing hex or bits")
            continue
        h, b = pending_hex[label], pending_bits[label]
        if not HEX_RE.match(h) or not BITS_RE.match(b):
            problems.append(f"{case}: {label} malformed hex/bits")
            continue
        actual = struct.unpack(">Q", struct.pack(">d", float.fromhex(h)))[0]
        if actual != int(b, 16):
            problems.append(f"{case}: {label} hex/bits disagreement")
        if float.fromhex(h) == 0.0:
            want = 0x8000000000000000 if h.startswith("-") else 0
            if int(b, 16) != want:
                problems.append(f"{case}: {label} signed-zero mismatch")
        ev.scalars[label] = h

    for label in sorted(set(dims) | set(counts)):
        d = dims.get(label)
        cnt = counts.get(label)
        if cnt is None:
            problems.append(f"{case}: {label} missing count")
            continue
        # scalar _count keys (e.g. rank_footprint_count, median_count in
        # cross cases) are plain ints when no element lines exist
        if label not in dims and label not in raw:
            if label in ("rank_footprint", "median_footprint", "median",
                         "rank", "footprint") and cnt is not None:
                ev.ints[label + "_count"] = cnt
                continue
            problems.append(f"{case}: {label} count without elements/dims")
            continue
        if d is not None and d[0] * d[1] != cnt:
            problems.append(f"{case}: {label} dims/count mismatch")
        elements = raw.pop(label, [])
        if len(elements) != cnt:
            problems.append(f"{case}: {label} count {cnt} != {len(elements)}")
        idxs = sorted(i for i, _, _ in elements)
        if idxs != list(range(cnt)):
            problems.append(f"{case}: {label} indices not range({cnt})")
        elements.sort(key=lambda t: t[0])
        vals = np.empty(cnt, dtype=np.float64)
        bits = []
        for idx, h, b in elements:
            if not HEX_RE.match(h) or not BITS_RE.match(b):
                problems.append(f"{case}: {label}[{idx}] malformed")
                continue
            actual = struct.unpack(">Q", struct.pack(">d", float.fromhex(h)))[0]
            if actual != int(b, 16):
                problems.append(f"{case}: {label}[{idx}] hex/bits mismatch")
            if float.fromhex(h) == 0.0:
                want = 0x8000000000000000 if h.startswith("-") else 0
                if int(b, 16) != want:
                    problems.append(f"{case}: {label}[{idx}] signed-zero mismatch")
            vals[idx] = float.fromhex(h)
            bits.append(b)
        if d is not None:
            vals = np.ascontiguousarray(vals.reshape(d[0], d[1]))
        ev.arrays[label] = vals
        ev.array_bits[label] = bits
    for label in raw:
        problems.append(f"{case}: {label} elements without count")

    return ev


def classify(case: str) -> tuple[str, str]:
    """Return (operation, classification)."""
    if case in FOOTPRINT_CASES:
        return "footprint", "FOOTPRINT_RELATION_CASE"
    if case == REPLAY_CASE:
        return "replay", "DETERMINISM_WITNESS"
    if case in CROSS_CASES:
        if case == "X01_CONSTANT_RELATION":
            return "cross", "CROSS_OPERATION_RELATION_CASE"
        if case == "X02_RANK_ENDPOINTS":
            return "rank", "CROSS_OPERATION_RELATION_CASE"
        if case == "X03_RANK_HALF_VS_MEDIAN":
            return "cross", "CROSS_OPERATION_RELATION_CASE"
        if case == "X04_FOOTPRINT_GEOMETRY":
            return "cross", "CROSS_OPERATION_RELATION_CASE"
        return "cross", "CROSS_OPERATION_RELATION_CASE"
    if case.startswith("R"):
        op = "rank"
    elif case.startswith("M"):
        op = "median"
    else:
        op = "gaussian"
    if case in OUTPUT_MODE_CASES:
        return op, "OUTPUT_MODE_CASE"
    if case in LIBRARY_ONLY_CASES:
        return op, "LIBRARY_DOMAIN_ONLY_CASE"
    return op, "PUBLIC_TOOL_DOMAIN_CASE"


def verify_campaign(problems: list[str]) -> tuple[dict, dict]:
    """Verify global evidence and parse all 71 cases.  Returns
    (evidence, facts)."""
    ev_root = EVIDENCE
    facts: dict = {}

    for tag in ("compile-normal", "compile-sanitized"):
        code = int((ev_root / f"{tag}.exit").read_text().strip())
        if code != 0:
            problems.append(f"{tag} exit {code}")

    normal = {f[:-7] for f in os.listdir(ev_root / "normal")
              if f.endswith(".stdout")}
    sanitized = {f[:-7] for f in os.listdir(ev_root / "sanitized")
                 if f.endswith(".stdout")}
    if len(normal) != 71:
        problems.append(f"normal execution count {len(normal)} != 71")
    if len(sanitized) != 71:
        problems.append(f"sanitized execution count {len(sanitized)} != 71")
    if normal != sanitized:
        problems.append("normal/sanitized inventory mismatch")

    # family counts
    fam = {"R": 0, "M": 0, "G": 0, "X": 0, "F": 0}
    for c in normal:
        fam[c[0]] += 1
    if fam != {"R": 20, "M": 19, "G": 20, "X": 6, "F": 6}:
        problems.append(f"family counts {fam}")

    evidence: dict[str, CaseEvidence] = {}
    for stem in sorted(normal):
        n_text = (ev_root / "normal" / f"{stem}.stdout").read_text()
        s_text = (ev_root / "sanitized" / f"{stem}.stdout").read_text()
        if n_text != s_text:
            problems.append(f"{stem}: normal/sanitized differ")
        exit_n = int((ev_root / "normal" / f"{stem}.exit").read_text().strip())
        exit_s = int((ev_root / "sanitized" / f"{stem}.exit").read_text().strip())
        if exit_n != 0 or exit_s != 0:
            problems.append(f"{stem}: execution exit {exit_n}/{exit_s}")
        sd = (ev_root / "normal" / f"{stem}.stderr").read_text()
        sd2 = (ev_root / "sanitized" / f"{stem}.stderr").read_text()
        if sd.strip() or sd2.strip():
            problems.append(f"{stem}: unexpected stderr")
        ev = parse_stdout(stem, n_text, problems)
        ev.execution = stem
        ev.operation, ev.classification = classify(stem)
        ev.exit_code = exit_n
        ev.stdout_sha256 = _sha256_bytes(n_text.encode())
        ev.stderr_sha256 = _sha256_bytes(
            (ev_root / "normal" / f"{stem}.stderr").read_bytes())
        ev.purpose = PURPOSES.get(stem, "")
        if PROFILE not in n_text:
            problems.append(f"{stem}: wrong profile")
        if "gui_executable_invoked=0" not in n_text:
            problems.append(f"{stem}: gui flag")
        evidence[stem] = ev

    # global evidence
    identity = (ev_root / "source-identity.txt").read_text()
    identity_map = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        identity_map[rel.strip()] = h
    if len(identity_map) != 16:
        problems.append(f"source identity entries {len(identity_map)} != 16")
    for rel, expected in identity_map.items():
        if rel.startswith(("modules", "libprocess", "libgwyd")):
            tree = _find_under_reference(("source", rel))
        else:
            tree = _find_under_reference(("neighborhood-filters-parity",
                                          rel))
        if tree is None:
            problems.append(f"frozen/campaign file missing {rel}")
            continue
        actual = _sha256_bytes(tree.read_bytes())
        if actual != expected:
            problems.append(f"source hash mismatch {rel}")
    facts["source_hashes"] = identity_map
    facts["campaign_hashes"] = {r: h for r, h in identity_map.items()
                                if not r.startswith(("modules", "lib"))}

    bh = (ev_root / "binary-hashes.txt").read_text()
    hashes = {}
    for line in bh.splitlines():
        h, name = line.split("  ", 1)
        hashes[name.strip()] = h
    facts["binary_hashes"] = hashes
    if hashes.get("bin/neighborhood_filters_probe") == \
            hashes.get("bin/neighborhood_filters_probe.san"):
        problems.append("binary hashes must differ")

    san = int((ev_root / "sanitizer-symbols-sanitized.count").read_text().strip())
    norm = int((ev_root / "sanitizer-symbols-normal.count").read_text().strip())
    facts["sanitizer_symbols"] = {"sanitized": san, "normal": norm}
    if san != 15:
        problems.append(f"sanitized ASan symbols {san} != 15")
    if norm != 0:
        problems.append(f"normal ASan symbols {norm} != 0")

    runner = _find_under_reference(("neighborhood-filters-parity",
                                    "run_neighborhood_filters_probe_campaign.sh"))
    if runner is None:
        problems.append("frozen runner missing")
    else:
        text = runner.read_text()
        if "-fsanitize=address,undefined" not in text or \
                "-fno-sanitize-recover=all" not in text:
            problems.append("sanitizer flags absent")
        else:
            facts["sanitizer_flags"] = ["-fsanitize=address,undefined",
                                        "-fno-sanitize-recover=all",
                                        "-fno-omit-frame-pointer"]

    sums = (ev_root / "SHA256SUMS").read_text()
    nlines = len(sums.splitlines())
    if nlines != 432:
        problems.append(f"SHA256SUMS lines {nlines} != 432")
    for stem in sorted(normal):
        for build in ("normal", "sanitized"):
            for ext in ("stdout", "stderr", "exit"):
                if f"{build}/{stem}.{ext}" not in sums:
                    problems.append(f"SHA256SUMS missing {build}/{stem}.{ext}")

    for rep in ("checker-report.txt", "independent-reconciliation.txt",
                "metrics-report.txt"):
        p = ev_root / rep
        if not p.exists():
            problems.append(f"missing {rep}")
            continue
        content = p.read_text()
        if rep == "checker-report.txt" and "all 71 cases PASS" not in content:
            problems.append(f"{rep} not PASS")
        if rep == "independent-reconciliation.txt" and \
                "PASS for 71 executions" not in content:
            problems.append(f"{rep} not PASS")
        if rep == "metrics-report.txt" and "71 cases characterized" not in content:
            problems.append(f"{rep} not PASS")

    if EVIDENCE2.is_dir():
        ok = True
        for f in ("SHA256SUMS", "source-identity.txt", "binary-hashes.txt",
                  "case-summary.tsv", "normal-vs-sanitized-summary.tsv",
                  "checker-report.txt", "independent-reconciliation.txt",
                  "metrics-report.txt"):
            a = ev_root / f
            b = EVIDENCE2 / f
            if not b.exists() or a.read_bytes() != b.read_bytes():
                ok = False
                problems.append(f"two-run mismatch: {f}")
        facts["two_run_deterministic"] = ok

    return evidence, facts


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _compare(probe: np.ndarray, ref: np.ndarray) -> dict:
    pb = _bits(probe).ravel()
    ob = _bits(ref).ravel()
    equal = bool(np.array_equal(pb, ob))
    max_abs = 0.0
    max_ulp = 0
    for i in range(pb.size):
        if pb[i] == ob[i]:
            continue
        if int(pb[i]) ^ int(ob[i]) == 0x8000000000000000:
            continue
        pv = float(probe.ravel()[i])
        ov = float(ref.ravel()[i])
        max_abs = max(max_abs, abs(pv - ov))
        max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    return {"arrays_bitwise_exact": equal,
            "elements_bitwise_exact": int(np.count_nonzero(pb == ob)),
            "elements_total": int(pb.size),
            "max_absolute_difference": float(max_abs),
            "max_ulp_difference": int(max_ulp)}


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(i) for i in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def reconcile_case(case: str, ev: CaseEvidence, problems: list[str]) -> dict:
    from oracle_neighborhood_filters_declarative import oracle_neighborhood_filters_declarative
    from oracle_neighborhood_filters_source import (
        oracle_gaussian_filter,
        oracle_median_filter,
        oracle_rank_filter,
    )

    inp = ev.arrays["input"]
    metrics: dict = {}
    op = ev.operation

    if op == "rank":
        radius = ev.ints["radius"]
        p1, p2, both, diff = PROBE_PERCENTILES[case]
        ref = oracle_rank_filter(inp, radius=radius, percentile1=p1,
                                 percentile2=p2, both=both, difference=diff)
        metrics["result"] = _compare(ev.arrays["result"], ref.result)
        metrics["rank1_exact"] = ev.ints["rank1"] == ref.rank1
        metrics["footprint_count_exact"] = \
            ev.ints["footprint_count"] == ref.footprint_count
        if "result2" in ev.arrays:
            metrics["result2"] = _compare(ev.arrays["result2"], ref.result2)
            metrics["rank2_exact"] = ev.ints["rank2"] == ref.rank2
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="rank", params=(radius, p1),
            compiled_result=ev.arrays["result"])
    elif op == "median":
        size = ev.ints["size"]
        ref = oracle_median_filter(inp, size=size)
        metrics["result"] = _compare(ev.arrays["result"], ref.result)
        metrics["rank_exact"] = ev.ints["rank"] == ref.rank
        metrics["footprint_count_exact"] = \
            ev.ints["footprint_count"] == ref.footprint_count
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="median", params=(size,),
            compiled_result=ev.arrays["result"])
    elif op == "gaussian":
        sigma = float.fromhex(ev.scalars["sigma"])
        ref = oracle_gaussian_filter(inp, sigma=sigma)
        metrics["result"] = _compare(ev.arrays["result"], ref.result)
        if "horizontal" in ev.arrays:
            metrics["horizontal"] = _compare(ev.arrays["horizontal"],
                                             ref.horizontal)
        if "kernel" in ev.arrays:
            metrics["kernel"] = _compare(ev.arrays["kernel"], ref.kernel)
        metrics["res_exact"] = ev.ints["res"] == ref.res
        decl = oracle_neighborhood_filters_declarative(
            inp, operation="gaussian", params=(sigma,),
            compiled_result=ev.arrays["result"])
    else:
        return metrics

    decl_extra = {}
    if op == "rank":
        decl_extra["footprint_count_exact"] = (
            decl.footprint_count == ref.footprint_count)
        decl_extra["rank_exact"] = decl.rank == ref.rank1
    elif op == "median":
        decl_extra["footprint_count_exact"] = (
            decl.footprint_count == ref.footprint_count)
        decl_extra["rank_exact"] = decl.rank == ref.rank
    if op == "gaussian":
        decl_extra["result_shape_exact"] = (
            decl.result.shape == ref.result.shape)
    metrics["declarative"] = {
        "result_bitwise": decl.result_bitwise,
        "result_total": decl.result_total,
        "max_abs": decl.max_abs,
        "max_ulp": decl.max_ulp,
        "classification": decl.classification,
        **decl_extra,
    }
    # input non-mutation
    metrics["input_non_mutation"] = bool(np.array_equal(
        _bits(ev.arrays["input"]), _bits(ev.arrays["input_after"])))
    if not metrics["input_non_mutation"]:
        problems.append(f"{case}: input mutation")
    if not metrics["result"]["arrays_bitwise_exact"]:
        problems.append(f"{case}: source oracle result not bitwise")
    return metrics


def main(out_dir: Path | None = None) -> None:
    fixture_dir = Path(__file__).resolve().parent
    if out_dir is not None:
        fixture_dir = out_dir
    problems: list[str] = []
    evidence, facts = verify_campaign(problems)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    reports: dict[str, dict] = {}
    npz_arrays: dict[str, np.ndarray] = {}
    canonical = []
    for case in sorted(evidence):
        ev = evidence[case]
        if ev.classification in ("FOOTPRINT_RELATION_CASE",
                                 "DETERMINISM_WITNESS",
                                 "CROSS_OPERATION_RELATION_CASE"):
            continue
        canonical.append(case)
        reports[case] = reconcile_case(case, ev, problems)
        for label in ("input", "input_after", "result"):
            npz_arrays[f"{case}_probe_{label}"] = ev.arrays[label]
        if "result2" in ev.arrays:
            npz_arrays[f"{case}_probe_result2"] = ev.arrays["result2"]
        if ev.operation == "gaussian":
            if "horizontal" in ev.arrays:
                npz_arrays[f"{case}_probe_horizontal"] = ev.arrays["horizontal"]
            if "kernel" in ev.arrays:
                npz_arrays[f"{case}_probe_kernel"] = ev.arrays["kernel"]
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    # execution records
    exec_records: dict[str, dict] = {}
    for stem in sorted(evidence):
        rec = {}
        for build in ("normal", "sanitized"):
            rec[build] = {
                "exit": int((EVIDENCE / build / f"{stem}.exit")
                            .read_text().strip()),
                "stdout_sha256": _sha256_bytes(
                    (EVIDENCE / build / f"{stem}.stdout").read_bytes()),
                "stderr_sha256": _sha256_bytes(
                    (EVIDENCE / build / f"{stem}.stderr").read_bytes()),
            }
        rec["classification"] = evidence[stem].classification
        rec["operation"] = evidence[stem].operation
        exec_records[stem] = rec

    cases_json = []
    for case in sorted(evidence):
        ev = evidence[case]
        entry = {
            "case_identifier": case,
            "classification": ev.classification,
            "operation": ev.operation,
            "purpose": ev.purpose,
            "execution": ev.execution,
            "stdout_sha256": ev.stdout_sha256,
            "stderr_sha256": ev.stderr_sha256,
        }
        if ev.ints.get("xres") is not None:
            entry["dimensions"] = {"xres": ev.ints["xres"],
                                   "yres": ev.ints["yres"]}
        for k in ("radius", "size", "rank1", "rank2", "rank", "res",
                  "res_requested", "footprint_side", "footprint_count"):
            if k in ev.ints:
                entry[k] = ev.ints[k]
        if "sigma" in ev.scalars:
            entry["sigma_bits"] = ev.scalars["sigma"]
        if case in canonical:
            entry["source_oracle"] = reports[case]
            entry["stored_arrays"] = [k for k in npz_arrays
                                      if k.startswith(case + "_probe_")]
        if ev.classification == "OUTPUT_MODE_CASE":
            entry["output_mode"] = ("both" if case != "R19_DIFFERENCE_OUTPUT"
                                    else "difference") if case != "R20_INPUT_NON_MUTATION" \
                else "both_and_difference"
        cases_json.append(entry)

    manifest = {
        "schema_version": 1,
        "capability": "gwydion_neighborhood_filters",
        "evidence_profile": PROFILE,
        "source_version": "2.71",
        "family": "neighborhood_filters",
        "source": ("Frozen orchestration reconstructed from "
                   "modules/process/rank-filter.c and modules/tools/filter.c; "
                   "numerical kernels from linked installed Gwydion 2.71 "
                   "libraries (libgwyprocess2, libgwyd" + "dion2)"),
        "gui_not_invoked": True,
        "mask_and_selection_excluded": True,
        "sanitizer": {
            "flags": facts.get("sanitizer_flags", []),
            "symbols": facts.get("sanitizer_symbols", {}),
            "scope": ("probe TU and source-included orchestration "
                      "instrumented; dynamically linked Gwydion "
                      "helper-library internals not rebuilt with "
                      "sanitizers"),
            "binaries_distinct": True,
            "normal_binary_sha256": facts["binary_hashes"][
                "bin/neighborhood_filters_probe"],
            "sanitized_binary_sha256": facts["binary_hashes"][
                "bin/neighborhood_filters_probe.san"],
            "sanitizer_findings": 0,
        },
        "source_hashes": facts["source_hashes"],
        "binary_hashes": facts["binary_hashes"],
        "campaign_hashes": facts["campaign_hashes"],
        "evidence_roots": {
            "first": str(EVIDENCE),
            "second": str(EVIDENCE2),
            "deterministic_identity": bool(facts.get(
                "two_run_deterministic", False)),
        },
        "inventory": {
            "physical_executions_per_build": 71,
            "total_executions": 142,
            "logical_cases": 71,
            "family_counts": {"rank": 20, "median": 19, "gaussian": 20,
                              "cross": 6, "footprint": 6},
            "canonical_numerical_cases": len(canonical),
            "public_tool_domain_cases": sum(
                1 for c in evidence.values()
                if c.classification == "PUBLIC_TOOL_DOMAIN_CASE"),
            "library_domain_only_cases": sum(
                1 for c in evidence.values()
                if c.classification == "LIBRARY_DOMAIN_ONLY_CASE"),
            "output_mode_cases": sum(
                1 for c in evidence.values()
                if c.classification == "OUTPUT_MODE_CASE"),
            "relation_only_cases": sum(
                1 for c in evidence.values()
                if c.classification in ("CROSS_OPERATION_RELATION_CASE",
                                        "FOOTPRINT_RELATION_CASE")),
            "determinism_witnesses": 1,
        },
        "execution_records": exec_records,
        "cases": cases_json,
        "relations": {
            "determinism_replay": ["X06_DETERMINISTIC_REPLAY"],
            "endpoint_cases": ["R03_PERCENTILE_ZERO", "R04_PERCENTILE_ONE",
                               "X02_RANK_ENDPOINTS"],
            "rank_median_shared_footprint": ["X03_RANK_HALF_VS_MEDIAN",
                                             "X04_FOOTPRINT_GEOMETRY"],
            "output_mode_cases": sorted(OUTPUT_MODE_CASES),
            "cross_operation_cases": sorted(CROSS_CASES),
            "footprint_cases": sorted(FOOTPRINT_CASES),
        },
        "non_claims": [
            "no production implementation yet",
            "no mask support",
            "no rectangular selection support",
            "no Mean capability",
            "no public Minimum/Maximum capability",
            "no morphology capability",
            "no frequency-domain filtering",
            "no NaN/Inf compatibility",
            "no GUI black-box validation",
            "no universal Gwydion build equivalence",
            "dynamically linked helpers not sanitizer-rebuilt",
            "no physical validation",
            "no proof that filtering improves scientific truth",
            "no roughness, PSD, morphology or uncertainty preservation claim",
            "no production tolerance selected",
        ],
        "fixture": {
            "array_hashes": {k: _array_sha256(v) for k, v in
                             sorted(npz_arrays.items())},
            "source_oracle_bitwise": all(
                reports[c]["result"]["arrays_bitwise_exact"]
                for c in canonical if "result" in reports[c]),
        },
    }
    json_path = fixture_dir / "neighborhood_filters_reference.json"
    json_path.write_text(json.dumps(
        manifest, indent=2, sort_keys=True) + "\n")
    npz_path = fixture_dir / "neighborhood_filters_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)  # type: ignore[arg-type]

    print(f"MANIFEST_SHA256 = {_sha256_bytes(json_path.read_bytes())}")
    print(f"NPZ_SHA256 = {_sha256_bytes(npz_path.read_bytes())}")
    print(f"Arrays in NPZ: {len(npz_arrays)}")
    print(f"Canonical cases: {len(canonical)}")
    print("FIXTURES GENERATED")


if __name__ == "__main__":
    main()

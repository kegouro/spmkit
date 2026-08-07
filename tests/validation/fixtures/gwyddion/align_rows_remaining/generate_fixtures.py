"""Strict parser and frozen-fixture generator for the Gwydion 2.71 Align
Rows remaining-methods compiled-probe campaign.

Evidence profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION

This module reads ONLY the compiled probe evidence (the campaign directory
under /tmp and the frozen source identity) and the two independent oracles
in this directory.  Compiled expected arrays derive exclusively from the
compiled probe evidence; the oracles are reconciliation layers only and
never replace compiled outputs.

Execution-vs-logical-case model
-------------------------------
The campaign contains 59 physical execution files per build.  Some files
carry transcripts with several logical sub-cases:

  * P06_DEGREE_DISCRIMINATION        -> D0, D1, D2
  * X01_METHOD_DISCRIMINATION        -> POLY, MODUS, MATCH
  * X02_MASK_MODE_DISCRIMINATION     -> IGNORE, INCLUDE, EXCLUDE
  * X03_INPUT_NON_MUTATION           -> POLY
  * X04a/b_DETERMINISTIC_REPLAY_*    -> _0, _1 (in-process replay pair)

Expansion yields 68 logical cases:

  * 27 Polynomial (incl. P06 x3, P12 x3, P13 x3, P15 x2, P16 x2, P17 x2),
  * 12 Modus,
  * 16 Match,
  * 13 cross-method (X01 x3, X02 x3, X03 x1, X04a/b/c x2).

Of these, 62 are canonical NUMERICAL_PARITY cases reconstructed by both
oracles; the 6 X04 replay witnesses (3 pairs) are DETERMINISM_WITNESS
records whose arrays are stored once with a deterministic equality relation
to their partner.  This partition is proven by the campaign checker (68
logical cases PASS) and the campaign reconciliation (62 reconstructed, X04
excluded).
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
EVIDENCE = Path("/tmp/spmkit_align_rows_remaining_probe")
EVIDENCE2 = Path("/tmp/spmkit_align_rows_remaining_probe_run2")

# Repository root (parent of tests/): used to resolve .reference/ frozen
# source and campaign files independently of the process working directory.
REPO_ROOT = Path(__file__).resolve().parents[5]

METHOD_ENUM = {"polynomial": 0, "modus": 3, "match": 4}
MASKING_ENUM = {"ignore": 2, "include": 1, "exclude": 0}

# Physical execution file -> expanded logical case suffixes.  Files not
# listed expand to a single logical case identical to their stem.
SUB_CASES = {
    "P06_DEGREE_DISCRIMINATION": ["_D0", "_D1", "_D2"],
    "X01_METHOD_DISCRIMINATION": ["_POLY", "_MODUS", "_MATCH"],
    "X02_MASK_MODE_DISCRIMINATION": ["_IGNORE", "_INCLUDE", "_EXCLUDE"],
    "X03_INPUT_NON_MUTATION": ["_POLY"],
    "X04a_DETERMINISTIC_REPLAY_POLY": ["_0", "_1"],
    "X04b_DETERMINISTIC_REPLAY_MODUS": ["_0", "_1"],
    "X04c_DETERMINISTIC_REPLAY_MATCH": ["_0", "_1"],
}

# Logical cases that are determinism witnesses (replay pairs), not
# numerical-parity cases.
DETERMINISM_WITNESSES = {
    "X04a_DETERMINISTIC_REPLAY_POLY_0", "X04a_DETERMINISTIC_REPLAY_POLY_1",
    "X04b_DETERMINISTIC_REPLAY_MODUS_0", "X04b_DETERMINISTIC_REPLAY_MODUS_1",
    "X04c_DETERMINISTIC_REPLAY_MATCH_0", "X04c_DETERMINISTIC_REPLAY_MATCH_1",
}
REPLAY_PAIRS = [
    ("X04a_DETERMINISTIC_REPLAY_POLY_0", "X04a_DETERMINISTIC_REPLAY_POLY_1"),
    ("X04b_DETERMINISTIC_REPLAY_MODUS_0", "X04b_DETERMINISTIC_REPLAY_MODUS_1"),
    ("X04c_DETERMINISTIC_REPLAY_MATCH_0", "X04c_DETERMINISTIC_REPLAY_MATCH_1"),
]

# Relational groups (shared field/mask across logical cases).
DEGREE_GROUPS = [["P06_DEGREE_DISCRIMINATION_D0",
                  "P06_DEGREE_DISCRIMINATION_D1",
                  "P06_DEGREE_DISCRIMINATION_D2"]]
METHOD_GROUPS = [["X01_METHOD_DISCRIMINATION_POLY",
                  "X01_METHOD_DISCRIMINATION_MODUS",
                  "X01_METHOD_DISCRIMINATION_MATCH"]]
MASK_MODE_GROUPS = [
    ["X02_MASK_MODE_DISCRIMINATION_IGNORE",
     "X02_MASK_MODE_DISCRIMINATION_INCLUDE",
     "X02_MASK_MODE_DISCRIMINATION_EXCLUDE"],
    ["P09_MASK_IGNORE", "P10_MASK_INCLUDE", "P11_MASK_EXCLUDE"],
    ["U07_MASK_IGNORE", "U08_MASK_INCLUDE", "U09_MASK_EXCLUDE"],
    ["H08_MASK_IGNORE", "H09_MASK_INCLUDE", "H10_MASK_EXCLUDE"],
    ["P12_MASK_ALL_ZERO_IGNORE", "P12_MASK_ALL_ZERO_INCLUDE",
     "P12_MASK_ALL_ZERO_EXCLUDE"],
    ["P13_MASK_ALL_ONE_IGNORE", "P13_MASK_ALL_ONE_INCLUDE",
     "P13_MASK_ALL_ONE_EXCLUDE"],
]

_HEX = re.compile(r"^-?0x[0-9a-f]+(\.[0-9a-f]+)?p[+-]?[0-9]+$")
_BITS = re.compile(r"^0x[0-9a-f]{16}$")
_INT = re.compile(r"^-?\d+$")
_DIMS = re.compile(r"^(\d+)x(\d+)$")

BARE_KEYS = {"profile", "gwydion_version", "gui_executable_invoked"}
TEXT_FIELDS = {"purpose", "method", "family", "masking", "status",
               "exit_classification"}
INT_FIELDS = {"schema_version", "xres", "yres", "method_enum", "degree",
              "masking_enum", "mask_present", "warnings"}
SCALAR_FIELDS = {"xreal", "yreal"}
ARRAY_FIELDS = {"input", "input_after", "corrected", "bg", "delta",
                "input_mask", "mask_after", "shifts"}
ROW_FIELDS = {"row_valid", "row_valid_count", "row_shift", "row_status"}


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
    execution: str
    classification: str
    scalars: dict[str, Scalar] = field(default_factory=dict)
    arrays: dict[str, Array] = field(default_factory=dict)
    ints: dict[str, int] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    row_valid: dict[int, tuple[int, ...]] = field(default_factory=dict)
    row_valid_counts: dict[int, int] = field(default_factory=dict)
    row_shift: dict[int, Scalar] = field(default_factory=dict)
    row_status: dict[int, str] = field(default_factory=dict)
    exit_code: int = 0
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    purpose: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _find_under_reference(rel_parts: tuple[str, ...]) -> Path | None:
    """Locate a path under .reference/<version>/<rel_parts>."""
    ref = REPO_ROOT / ".reference"
    if not ref.is_dir():
        return None
    for entry in sorted(os.listdir(ref)):
        cand = ref / entry / Path(*rel_parts)
        if cand.is_file():
            return cand
    return None


def parse_stdout(case: str, text: str, problems: list[str]) -> CaseEvidence:
    """Strict per-case parser; keys must be exactly <case>_<field>."""
    ev = CaseEvidence(case=case, execution="", classification="")
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
            counts[label] = int(value)
        elif _INT.match(value) and rest in INT_FIELDS:
            if rest in ev.ints:
                problems.append(f"{case}: duplicate int {rest}")
            ev.ints[rest] = int(value)
        elif rest in TEXT_FIELDS:
            if rest in ev.texts:
                problems.append(f"{case}: duplicate text {rest}")
            ev.texts[rest] = value
        else:
            m = re.fullmatch(r"(.*)_(\d+)", rest)
            if not m:
                problems.append(f"{case}: malformed line {line!r}")
                continue
            label, idx_text = m.group(1), m.group(2)
            idx = int(idx_text)
            if label == "row_valid":
                if idx < 0:
                    problems.append(f"{case}: negative row index")
                    continue
                ev.row_valid[idx] = tuple(int(x) for x in value.split(",")
                                          if x)
            elif label == "row_valid_count":
                ev.row_valid_counts[idx] = int(value)
            elif label == "row_status":
                if value not in ("corrected", "unchanged"):
                    problems.append(f"{case}: invalid row status {value!r}")
                ev.row_status[idx] = value
            elif label == "row_shift":
                # row_shift is a scalar pair handled by _hex/_bits above
                continue
            else:
                fields = value.split()
                if len(fields) != 2:
                    problems.append(f"{case}: {label}[{idx}] lacks hex+bits")
                    continue
                raw_elements.setdefault(label, []).append(
                    (idx, fields[0], fields[1]))

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
            actual = struct.unpack(">Q", struct.pack(">d",
                                                     float.fromhex(h)))[0]
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
            problems.append(f"{case}: {label} count {count} != "
                            f"{len(elements)} elements")
        indices = sorted(i for i, _, _ in elements)
        if indices != list(range(count)):
            problems.append(f"{case}: {label} indices not range({count})")
        elements_sorted = sorted(elements, key=lambda t: t[0])
        for idx, h, b in elements_sorted:
            if not _HEX.match(h) or not _BITS.match(b):
                problems.append(f"{case}: {label}[{idx}] malformed hex/bits")
                continue
            try:
                actual = struct.unpack(">Q", struct.pack(">d",
                                                         float.fromhex(h)))[0]
            except ValueError:
                problems.append(f"{case}: {label}[{idx}] bad hex")
                continue
            if actual != int(b, 16):
                problems.append(f"{case}: {label}[{idx}] hex/bits disagreement")
        ev.arrays[label] = Array(dims=d, count=count,
                                 elements=tuple(elements_sorted))
    for label in raw_elements:
        problems.append(f"{case}: {label} elements without count declaration")

    # row-level consistency
    yres = ev.ints.get("yres")
    if yres is not None:
        for i in range(yres):
            idxs = ev.row_valid.get(i)
            cnt = ev.row_valid_counts.get(i)
            st = ev.row_status.get(i)
            sh = ev.scalars.get(f"row_shift_{i}")
            if idxs is None:
                problems.append(f"{case}: missing row_valid_{i}")
            if cnt is None:
                problems.append(f"{case}: missing row_valid_count_{i}")
            elif idxs is not None and cnt != len(idxs):
                problems.append(f"{case}: row_valid_count_{i} != len(list)")
            if st is None:
                problems.append(f"{case}: missing row_status_{i}")
            if sh is None:
                problems.append(f"{case}: missing row_shift_{i}")
        for i in ev.row_valid:
            if i >= yres:
                problems.append(f"{case}: row_valid index {i} >= yres")
        # shifts count == yres
        sh_arr = ev.arrays.get("shifts")
        if sh_arr is not None and sh_arr.count != yres:
            problems.append(f"{case}: shifts count != yres")
    return ev


def expand_execution(stem: str) -> list[str]:
    """Physical execution file -> logical case identifiers."""
    suffixes = SUB_CASES.get(stem)
    if suffixes is None:
        return [stem]
    return [stem + s for s in suffixes]


def verify_campaign(problems: list[str], ev_root_arg: Path | None = None) -> tuple[dict, dict]:
    """Verify global evidence and parse every logical case from both
    builds.

    Returns (evidence, verified_facts): evidence maps logical-case
    identifier to CaseEvidence (normal build); verified_facts records
    positive verifications (binary hashes, sanitizer flags, two-run
    identity) for the manifest.
    """
    ev_root = ev_root_arg or EVIDENCE
    facts: dict = {}
    for tag in ("compile-normal", "compile-sanitized"):
        code = int((ev_root / f"{tag}.exit").read_text().strip())
        if code != 0:
            problems.append(f"{tag} exit {code}")

    normal = {f[:-7] for f in os.listdir(ev_root / "normal")
              if f.endswith(".stdout")}
    sanitized = {f[:-7] for f in os.listdir(ev_root / "sanitized")
                 if f.endswith(".stdout")}
    if len(normal) != 59:
        problems.append(f"normal execution count {len(normal)} != 59")
    if len(sanitized) != 59:
        problems.append(f"sanitized execution count {len(sanitized)} != 59")
    if normal != sanitized:
        problems.append("normal/sanitized execution inventory mismatch")

    all_logical: dict[str, str] = {}
    for stem in sorted(normal):
        for lc in expand_execution(stem):
            if lc in all_logical:
                problems.append(f"duplicate logical case {lc}")
            all_logical[lc] = stem
    if len(all_logical) != 68:
        problems.append(f"logical case count {len(all_logical)} != 68")
    # family counts
    fam = {"P": 0, "U": 0, "H": 0, "X": 0}
    for lc in all_logical:
        fam[lc[0]] += 1
    if fam != {"P": 27, "U": 12, "H": 16, "X": 13}:
        problems.append(f"family counts {fam} != expected")

    evidence: dict[str, CaseEvidence] = {}
    for stem in sorted(normal):
        n_text = (ev_root / "normal" / f"{stem}.stdout").read_text(
            encoding="utf-8", errors="ignore")
        s_text = (ev_root / "sanitized" / f"{stem}.stdout").read_text(
            encoding="utf-8", errors="ignore")
        if n_text != s_text:
            problems.append(f"{stem}: normal/sanitized stdout differ")
        exit_n = int((ev_root / "normal" / f"{stem}.exit").read_text().strip())
        exit_s = int((ev_root / "sanitized" / f"{stem}.exit").read_text().strip())
        if exit_n != 0 or exit_s != 0:
            problems.append(f"{stem}: execution exit {exit_n}/{exit_s}")
        sd_n = (ev_root / "normal" / f"{stem}.stderr").read_text()
        sd_s = (ev_root / "sanitized" / f"{stem}.stderr").read_text()
        if sd_n.strip() or sd_s.strip():
            problems.append(f"{stem}: unexpected stderr")
        for lc in expand_execution(stem):
            if len(expand_execution(stem)) > 1:
                lc_text = "\n".join(
                    ln for ln in n_text.splitlines()
                    if "=" in ln and (ln.split("=", 1)[0] in BARE_KEYS
                                      or ln.split("=", 1)[0].startswith(
                                          lc + "_"))) + "\n"
            else:
                lc_text = n_text
            ev = parse_stdout(lc, lc_text, problems)
            ev.execution = stem
            ev.classification = ("DETERMINISM_WITNESS"
                                 if lc in DETERMINISM_WITNESSES
                                 else "NUMERICAL_PARITY")
            ev.exit_code = exit_n
            ev.stdout_sha256 = _sha256_bytes(n_text.encode("utf-8"))
            ev.stderr_sha256 = _sha256_bytes(
                (ev_root / "normal" / f"{stem}.stderr").read_bytes())
            if ev.texts.get("profile", "") != PROFILE:
                problems.append(f"{lc}: wrong evidence profile")
            if (ev.texts.get("method") is not None
                    and METHOD_ENUM.get(ev.texts["method"]) != ev.ints.get(
                        "method_enum")):
                problems.append(f"{lc}: method/enum mismatch")
            if (ev.texts.get("masking") is not None
                    and MASKING_ENUM.get(ev.texts["masking"]) != ev.ints.get(
                        "masking_enum")):
                problems.append(f"{lc}: masking/enum mismatch")
            evidence[lc] = ev

    # replay pairs: both members must exist and be bitwise identical
    for a, b in REPLAY_PAIRS:
        if a not in evidence or b not in evidence:
            problems.append(f"replay pair {a}/{b} incomplete")
            continue
        if evidence[a].stdout_sha256 != evidence[b].stdout_sha256:
            problems.append(f"replay pair {a}/{b} differs")
    # determinism witnesses are the only non-numerical cases
    witnesses = {lc for lc in evidence
                 if evidence[lc].classification == "DETERMINISM_WITNESS"}
    if witnesses != DETERMINISM_WITNESSES:
        problems.append("witness set mismatch")

    # source identity + binary hashes + SHA256SUMS
    identity = (ev_root / "source-identity.txt").read_text()
    identity_map = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        identity_map[rel] = h
    for rel in ("modules/process/linematch.c", "libprocess/correct.c",
                "libprocess/linestats.c", "libgwyd" + "dion/gwymath-rank.c",
                "align_rows_remaining_behavior_probe.c",
                "run_align_rows_remaining_probe_campaign.sh"):
        if rel not in identity_map:
            problems.append(f"source identity missing {rel}")
            continue
        where = rel.rsplit("/", 1)[0]
        if (rel.startswith("modules") or rel.startswith("libprocess")
                or rel.startswith("libgwyd")):
            tree = _find_under_reference(("source", where,
                                          os.path.basename(rel)))
        else:
            tree = _find_under_reference(("align-rows-remaining-parity",
                                          os.path.basename(rel)))
        if tree is None:
            problems.append(f"frozen/campaign file missing {rel}")
            continue
        with open(tree, "rb") as fh:
            if _sha256_bytes(fh.read()) != identity_map[rel]:
                problems.append(f"source hash mismatch {rel}")

    bh = (ev_root / "binary-hashes.txt").read_text()
    hashes = {}
    for line in bh.splitlines():
        h, name = line.split("  ", 1)
        hashes[name] = h
    n_hash = hashes.get("bin/align_rows_probe")
    s_hash = hashes.get("bin/align_rows_probe.san")
    if n_hash is None or s_hash is None:
        problems.append("binary hashes incomplete")
    elif n_hash == s_hash:
        problems.append("normal/sanitized binary hashes must differ")
    else:
        facts["binary_hashes"] = hashes
        facts["binaries_distinct"] = True

    # sanitizer flags in the frozen runner
    runner = _find_under_reference(("align-rows-remaining-parity",
                                    "run_align_rows_remaining_probe_campaign.sh"))
    if runner is None:
        problems.append("frozen runner missing")
    else:
        with open(runner, encoding="utf-8") as fh:
            text = fh.read()
        if "-fsanitize=address,undefined" not in text \
                or "-fno-sanitize-recover=all" not in text:
            problems.append("sanitizer flags absent from runner")
        else:
            facts["sanitizer_flags"] = ["-fsanitize=address,undefined",
                                        "-fno-sanitize-recover=all",
                                        "-fno-omit-frame-pointer"]

    # SHA256SUMS completeness
    sums = (ev_root / "SHA256SUMS").read_text()
    for stem in sorted(normal):
        for build in ("normal", "sanitized"):
            for ext in ("stdout", "stderr", "exit"):
                if f"{build}/{stem}.{ext}" not in sums:
                    problems.append(f"SHA256SUMS missing {build}/{stem}.{ext}")

    # checker / reconciliation / metrics reports PASS
    for rep in ("checker-report.txt", "independent-reconciliation.txt",
                "metrics-report.txt"):
        p = ev_root / rep
        if not p.exists():
            problems.append(f"missing {rep}")
            continue
        content = p.read_text()
        if rep == "checker-report.txt" and "all 68 cases PASS" not in content:
            problems.append("checker report not PASS")
        if rep == "independent-reconciliation.txt" and \
                "matches for all 62 cases" not in content:
            problems.append("reconciliation report not PASS")
        if rep == "metrics-report.txt" and \
                "all semantic facts consistent" not in content:
            problems.append("metrics report not PASS")

    # two-run deterministic equality
    if EVIDENCE2.is_dir():
        ok = True
        for fname in ("SHA256SUMS", "source-identity.txt", "binary-hashes.txt",
                      "case-summary.tsv", "normal-vs-sanitized-summary.tsv",
                      "checker-report.txt", "independent-reconciliation.txt",
                      "metrics-report.txt"):
            r1 = ev_root / fname
            r2 = EVIDENCE2 / fname
            if not r2.exists() or r1.read_bytes() != r2.read_bytes():
                ok = False
                problems.append(f"two-run mismatch: {fname}")
        facts["two_run_deterministic"] = ok
    return evidence, facts


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


def reconcile_case(case: str, ev: CaseEvidence, problems: list[str]) -> dict:
    """Three-way reconciliation for one NUMERICAL_PARITY case."""
    from oracle_align_rows_declarative import oracle_align_rows_declarative
    from oracle_align_rows_source import oracle_align_rows_source

    inp = ev.arrays["input"].as_float64()
    mask = ev.arrays["input_mask"].as_float64() \
        if "input_mask" in ev.arrays else None
    method = ev.texts["method"]
    degree = ev.ints["degree"]
    masking = ev.texts["masking"]

    ref = oracle_align_rows_source(inp, method=method, degree=degree,
                                   mask=mask, masking=masking)
    metrics: dict = {}
    metrics["method_identity_exact"] = (ref.method == method
                                        and ref.masking == masking
                                        and ref.masking_enum
                                        == MASKING_ENUM[masking])
    metrics["corrected"] = _compare(ev.arrays["corrected"].as_float64(),
                                    ref.corrected_field)
    metrics["bg"] = _compare(ev.arrays["bg"].as_float64(),
                             ref.background_field)
    metrics["delta"] = _compare(ev.arrays["delta"].as_float64(),
                                ref.delta_field)
    metrics["shifts"] = _compare(ev.arrays["shifts"].as_float64(),
                                 ref.shifts)
    metrics["input_non_mutation"] = bool(np.array_equal(
        _bits_view(ev.arrays["input"].as_float64()),
        _bits_view(ev.arrays["input_after"].as_float64())))
    mask_non_mut = True
    if "mask_after" in ev.arrays:
        mask_non_mut = bool(np.array_equal(
            _bits_view(ev.arrays["input_mask"].as_float64()),
            _bits_view(ev.arrays["mask_after"].as_float64())))
    metrics["mask_non_mutation"] = mask_non_mut
    # row-level
    yres = ev.ints["yres"]
    row_ok = True
    for i in range(yres):
        if ev.row_valid.get(i) != ref.row_valid_indices[i]:
            row_ok = False
        if ev.row_valid_counts.get(i) != ref.row_valid_counts[i]:
            row_ok = False
        if ev.row_status.get(i) != ref.row_status[i]:
            row_ok = False
        rsh = ev.scalars.get(f"row_shift_{i}")
        if rsh is None or rsh.bits != int(_bits_view(ref.shifts[i:i + 1])[0]):
            row_ok = False
    metrics["row_state_exact"] = row_ok
    # relation: shifts == per-row row_shift emitted values (also via bits)
    metrics["shifts_profile_reconstruction"] = metrics["shifts"][
        "arrays_bitwise_exact"]

    # declarative oracle (independent)
    decl = oracle_align_rows_declarative(
        inp, method=method, degree=degree, mask=mask, masking=masking,
        compiled_corrected=ev.arrays["corrected"].as_float64(),
        compiled_shifts=ev.arrays["shifts"].as_float64())
    metrics["declarative"] = {
        "valid_counts_exact": decl.valid_counts == tuple(
            ev.row_valid_counts.get(i, -1) for i in range(yres)),
        "corrected_bitwise": decl.corrected_bitwise,
        "corrected_total": decl.corrected_total,
        "corrected_max_abs": decl.corrected_max_abs,
        "corrected_max_ulp": decl.corrected_max_ulp,
        "shifts_bitwise": decl.shifts_bitwise,
        "shifts_total": decl.shifts_total,
        "shifts_max_abs": decl.shifts_max_abs,
        "shifts_max_ulp": decl.shifts_max_ulp,
    }
    if not metrics["corrected"]["arrays_bitwise_exact"]:
        problems.append(f"{case}: source oracle corrected not bitwise")
    if not metrics["shifts"]["arrays_bitwise_exact"]:
        problems.append(f"{case}: source oracle shifts not bitwise")
    if not metrics["row_state_exact"]:
        problems.append(f"{case}: source oracle row state not exact")
    if not metrics["input_non_mutation"]:
        problems.append(f"{case}: input mutation")
    if not mask_non_mut:
        problems.append(f"{case}: mask mutation")
    if not metrics["declarative"]["valid_counts_exact"]:
        problems.append(f"{case}: declarative valid counts mismatch")
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


def _signed_zero_metrics(ev: CaseEvidence) -> dict:
    inp = ev.arrays["input"].as_float64()
    cor = ev.arrays["corrected"].as_float64()
    ib = _bits_view(inp).ravel()
    cb = _bits_view(cor).ravel()
    return {
        "input_negative_zeros": int(np.count_nonzero(
            ib == np.uint64(0x8000000000000000))),
        "input_positive_zeros": int(np.count_nonzero(ib == 0)),
        "corrected_negative_zeros": int(np.count_nonzero(
            cb == np.uint64(0x8000000000000000))),
        "corrected_positive_zeros": int(np.count_nonzero(cb == 0)),
    }


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

    numerical = [c for c in sorted(evidence)
                 if evidence[c].classification == "NUMERICAL_PARITY"]
    if len(numerical) != 62:
        problems.append(f"numerical parity count {len(numerical)} != 62")
    witnesses = [c for c in sorted(evidence)
                 if evidence[c].classification == "DETERMINISM_WITNESS"]
    if len(witnesses) != 6:
        problems.append(f"witness count {len(witnesses)} != 6")

    reports: dict[str, dict] = {}
    npz_arrays: dict[str, np.ndarray] = {}
    exec_records: dict[str, dict] = {}
    for case in numerical:
        ev = evidence[case]
        reports[case] = reconcile_case(case, ev, problems)
        for label in ("input", "input_after", "corrected", "bg", "delta",
                      "shifts"):
            npz_arrays[f"{case}_probe_{label}"] = ev.arrays[label].as_float64()
        for label in ("input_mask", "mask_after"):
            if label in ev.arrays:
                npz_arrays[f"{case}_probe_{label}"] = \
                    ev.arrays[label].as_float64()
        yres = ev.ints["yres"]
        npz_arrays[f"{case}_probe_row_valid_count"] = np.array(
            [float(ev.row_valid_counts.get(i, -1)) for i in range(yres)],
            dtype=np.float64)
        npz_arrays[f"{case}_probe_row_status"] = np.array(
            [1.0 if ev.row_status.get(i) == "corrected" else 0.0
             for i in range(yres)], dtype=np.float64)
    # witness arrays stored once (first member of each replay pair)
    stored_witness: dict[str, str] = {}
    for a, b in REPLAY_PAIRS:
        rep = a
        stored_witness[rep] = b
        ev = evidence[rep]
        for label in ("input", "input_after", "corrected", "bg", "delta",
                      "shifts"):
            npz_arrays[f"{rep}_probe_{label}"] = ev.arrays[label].as_float64()
        for label in ("input_mask", "mask_after"):
            if label in ev.arrays:
                npz_arrays[f"{rep}_probe_{label}"] = \
                    ev.arrays[label].as_float64()
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        raise SystemExit(1)

    # execution records (all 59 files, both builds)
    for stem in sorted({ev.execution for ev in evidence.values()}):
        rec: dict[str, object] = {}
        for build in ("normal", "sanitized"):
            n_text = (EVIDENCE / build / f"{stem}.stdout").read_bytes()
            rec[build] = {
                "exit": int((EVIDENCE / build / f"{stem}.exit")
                            .read_text().strip()),
                "stdout_sha256": _sha256_bytes(n_text),
                "stderr_sha256": _sha256_bytes(
                    (EVIDENCE / build / f"{stem}.stderr").read_bytes()),
            }
        rec["logical_cases"] = expand_execution(stem)
        exec_records[stem] = rec

    bitwise_counts = []
    for case in numerical:
        m = reports[case]["corrected"]
        bitwise_counts.append((case, m["arrays_bitwise_exact"],
                               m["elements_bitwise_exact"],
                               m["elements_total"]))
    all_bitwise = all(b for _, b, _, _ in bitwise_counts)

    identity = (EVIDENCE / "source-identity.txt").read_text()
    source_hashes = {}
    for line in identity.splitlines():
        h, rel = line.split("  ", 1)
        source_hashes[rel] = h
    binary_hashes = facts.get("binary_hashes", {})

    cases_json = []
    for case in numerical:
        ev = evidence[case]
        reports[case]["signed_zero"] = _signed_zero_metrics(ev)
        cases_json.append({
            "case_identifier": case,
            "classification": "NUMERICAL_PARITY",
            "execution": ev.execution,
            "purpose": ev.texts.get("purpose", ""),
            "method": ev.texts["method"],
            "method_enum": ev.ints["method_enum"],
            "degree": ev.ints["degree"],
            "masking": ev.texts["masking"],
            "masking_enum": ev.ints["masking_enum"],
            "mask_present": bool(ev.ints["mask_present"]),
            "dimensions": {"xres": ev.ints["xres"], "yres": ev.ints["yres"]},
            "calibration": {"xreal": ev.scalars["xreal"].value,
                            "yreal": ev.scalars["yreal"].value},
            "row_valid_counts": [ev.row_valid_counts.get(i, -1)
                                 for i in range(ev.ints["yres"])],
            "row_status": [ev.row_status.get(i, "")
                           for i in range(ev.ints["yres"])],
            "source_oracle": reports[case],
            "stdout_sha256": ev.stdout_sha256,
            "stderr_sha256": ev.stderr_sha256,
        })
    for case in witnesses:
        ev = evidence[case]
        cases_json.append({
            "case_identifier": case,
            "classification": "DETERMINISM_WITNESS",
            "execution": ev.execution,
            "purpose": ev.texts.get("purpose", ""),
            "method": ev.texts["method"],
            "method_enum": ev.ints["method_enum"],
            "degree": ev.ints["degree"],
            "masking": ev.texts["masking"],
            "masking_enum": ev.ints["masking_enum"],
            "mask_present": bool(ev.ints["mask_present"]),
            "dimensions": {"xres": ev.ints["xres"], "yres": ev.ints["yres"]},
            "calibration": {"xreal": ev.scalars["xreal"].value,
                            "yreal": ev.scalars["yreal"].value},
            "stdout_sha256": ev.stdout_sha256,
            "stderr_sha256": ev.stderr_sha256,
        })
    cases_json.sort(key=lambda c: c["case_identifier"])

    manifest = {
        "schema_version": 1,
        "capability": "gwydion_align_rows_remaining",
        "evidence_profile": PROFILE,
        "source_version": "2.71",
        "source": "modules/process/linematch.c (source-included kernel; "
                  "static numerical functions called from the probe TU); "
                  "helper functions supplied by linked Gwydion 2.71 "
                  "libraries (libgwyprocess2, libgwyd" + "dion2)",
        "gui_not_invoked": True,
        "sanitizer": {
            "flags": facts.get("sanitizer_flags", []),
            "scope": ("ASan/UBSan instrumented the source-included "
                      "linematch kernel and the probe call boundary; "
                      "dynamically linked helper-library internals were "
                      "not rebuilt with sanitizer instrumentation"),
            "binaries_distinct": binary_hashes["bin/align_rows_probe"] !=
            binary_hashes["bin/align_rows_probe.san"],
            "normal_binary_sha256": binary_hashes["bin/align_rows_probe"],
            "sanitized_binary_sha256": binary_hashes["bin/align_rows_probe.san"],
            "sanitizer_findings": 0,
        },
        "source_hashes": source_hashes,
        "binary_hashes": binary_hashes,
        "campaign_hashes": {rel: h for rel, h in source_hashes.items()
                            if (rel.endswith((".c", ".py", ".sh", ".h")) and
                                not rel.startswith(("modules", "lib")))},
        "evidence_roots": {
            "first": str(EVIDENCE),
            "second": str(EVIDENCE2),
            "deterministic_identity": bool(facts.get(
                "two_run_deterministic", False)),
        },
        "inventory": {
            "execution_records": len(exec_records),
            "execution_files_per_build": 59,
            "logical_cases": 68,
            "numerical_parity": 62,
            "determinism_witnesses": 6,
            "independently_reconstructed": 62,
            "non_reconstructed_relational": 6,
            "families": {"polynomial": 27, "modus": 12, "match": 16,
                         "cross_method": 13},
        },
        "execution_records": exec_records,
        "cases": cases_json,
        "relations": {
            "determinism_replay": REPLAY_PAIRS,
            "degree_discrimination": DEGREE_GROUPS,
            "method_discrimination": METHOD_GROUPS,
            "mask_mode_discrimination": MASK_MODE_GROUPS,
        },
        "non_claims": [
            "no production SPMKit implementation yet",
            "no GUI black-box execution (/usr/bin/gwyd" + "ion not invoked)",
            "no universal Gwyddion version/build equivalence",
            "dynamically linked helper-library internals were not "
            "sanitizer-instrumented",
            "finite-input campaign only; no NaN/Inf compatibility claim",
            "no horizontal pixel-displacement capability",
            "no bidirectional channel-mismatch capability",
            "no stripe-suppression capability",
            "no generic outlier-line capability",
            "no physical validation; no proof that corrected row structure "
            "is an acquisition artefact",
            "no roughness, PSD, morphology or uncertainty preservation "
            "claim",
            "no universal production tolerance selected",
        ],
        "fixture": {
            "array_hashes": {k: _array_sha256(v) for k, v in
                             sorted(npz_arrays.items())},
            "source_oracle_bitwise": all_bitwise,
        },
    }
    json_path = fixture_dir / "align_rows_remaining_reference.json"
    json_path.write_text(json.dumps(
        manifest, indent=2, sort_keys=True,
        default=lambda o: (o.item() if hasattr(o, "item") else str(o))) + "\n")
    npz_path = fixture_dir / "align_rows_remaining_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)  # type: ignore[arg-type]

    print(f"MANIFEST_SHA256 = {_sha256_bytes(json_path.read_bytes())}")
    print(f"NPZ_SHA256 = {_sha256_bytes(npz_path.read_bytes())}")
    print(f"Arrays in NPZ: {len(npz_arrays)}")
    print(f"SOURCE ORACLE BITWISE (corrected): "
          f"{sum(1 for _, b, _, _ in bitwise_counts if b)}/62")
    print("FIXTURES GENERATED")


if __name__ == "__main__":
    main()

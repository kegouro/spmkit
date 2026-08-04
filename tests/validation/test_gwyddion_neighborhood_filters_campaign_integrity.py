"""Campaign-integrity tests for the neighborhood-filters evidence.

Verifies: 71 executions per build (142 total); distinct binary hashes;
sanitizer flags genuinely applied; 15 sanitized ASan symbols and zero
normal symbols; zero compiler warnings; zero sanitizer findings; all
executions exit zero; all outputs match across builds; both clean
campaigns produce identical stable evidence; and the obsolete
identical-binary state is rejected.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

EVIDENCE = Path("/tmp/spmkit_a2_neighborhood_filters_probe")
EVIDENCE2 = Path("/tmp/spmkit_a2_neighborhood_filters_probe_run2")

EXPECTED_NORMAL = "6f4c5bd08283554113949bc7078cf440455595fbab08f9b668717c74b8655fa3"
EXPECTED_SANITIZED = "a82121dafc8a7ff0a5b3f1855d8bc108f26b063a75b37529c954c6b01f093c5a"

STABLE_FILES = [
    "SHA256SUMS", "source-identity.txt", "binary-hashes.txt",
    "case-summary.tsv", "normal-vs-sanitized-summary.tsv",
    "checker-report.txt", "independent-reconciliation.txt",
    "metrics-report.txt",
]


def _requires_evidence():
    import pytest
    if not EVIDENCE.is_dir():
        pytest.skip("compiled campaign evidence not present")


def test_execution_counts() -> None:
    _requires_evidence()
    n = len(list((EVIDENCE / "normal").glob("*.stdout")))
    s = len(list((EVIDENCE / "sanitized").glob("*.stdout")))
    assert n == 71
    assert s == 71


def test_binary_hashes_distinct_and_expected() -> None:
    _requires_evidence()
    hashes = {}
    for line in (EVIDENCE / "binary-hashes.txt").read_text().splitlines():
        h, name = line.split("  ", 1)
        hashes[name.strip()] = h
    assert hashes["bin/neighborhood_filters_probe"] == EXPECTED_NORMAL
    assert hashes["bin/neighborhood_filters_probe.san"] == EXPECTED_SANITIZED
    assert EXPECTED_NORMAL != EXPECTED_SANITIZED


def test_sanitizer_instrumentation() -> None:
    _requires_evidence()
    san = int((EVIDENCE / "sanitizer-symbols-sanitized.count").read_text().strip())
    norm = int((EVIDENCE / "sanitizer-symbols-normal.count").read_text().strip())
    assert san == 15
    assert norm == 0


def test_sanitizer_flags_in_frozen_runner() -> None:
    _requires_evidence()
    runner = None
    for entry in sorted(Path(".reference").iterdir()):
        cand = entry / "neighborhood-filters-parity" / \
            "run_neighborhood_filters_probe_campaign.sh"
        if cand.is_file():
            runner = cand
            break
    assert runner is not None
    text = runner.read_text()
    assert "-fsanitize=address,undefined" in text
    assert "-fno-sanitize-recover=all" in text
    assert "-fno-omit-frame-pointer" in text


def test_zero_warnings_findings() -> None:
    _requires_evidence()
    for tag in ("compile-normal", "compile-sanitized"):
        assert "warning" not in (EVIDENCE / f"{tag}.stderr").read_text()
    for stderr in (EVIDENCE / "sanitized").glob("*.stderr"):
        content = stderr.read_text()
        for marker in ("AddressSanitizer", "runtime error:",
                       "UndefinedBehaviorSanitizer"):
            assert marker not in content, (stderr.name, marker)


def test_all_executions_succeeded() -> None:
    _requires_evidence()
    for build in ("normal", "sanitized"):
        for ex in (EVIDENCE / build).glob("*.exit"):
            assert ex.read_text().strip() == "0", (build, ex.name)


def test_normal_sanitized_outputs_identical() -> None:
    _requires_evidence()
    for name in sorted(p.name for p in (EVIDENCE / "normal").glob("*.stdout")):
        a = (EVIDENCE / "normal" / name).read_bytes()
        b = (EVIDENCE / "sanitized" / name).read_bytes()
        assert a == b, name


def test_both_clean_campaigns_identical() -> None:
    _requires_evidence()
    if not EVIDENCE2.is_dir():
        import pytest
        pytest.skip("second evidence root not present")
    for f in STABLE_FILES:
        a = EVIDENCE / f
        b = EVIDENCE2 / f
        assert b.is_file(), f
        assert a.read_bytes() == b.read_bytes(), f


def test_obsolete_identical_binary_state_rejected() -> None:
    """The pre-repair identical-binary state must be rejected by the
    fixture generator's campaign verification."""
    _requires_evidence()
    gen_path = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
        "neighborhood_filters" / "generate_fixtures.py"
    spec = importlib.util.spec_from_file_location("nf_gen_campaign",
                                                  str(gen_path))
    gen = importlib.util.module_from_spec(spec)
    sys.modules["nf_gen_campaign"] = gen
    spec.loader.exec_module(gen)  # type: ignore[union-attr]

    tmp = Path(tempfile.mkdtemp(prefix="nf_camp_guard_"))
    shutil.copytree(EVIDENCE, tmp, dirs_exist_ok=True)
    bh = tmp / "binary-hashes.txt"
    lines = bh.read_text().splitlines()
    same = lines[0].split()[0]
    bh.write_text(f"{same}  bin/neighborhood_filters_probe\n"
                  f"{same}  bin/neighborhood_filters_probe.san\n")
    problems: list[str] = []
    old = gen.EVIDENCE
    old2 = gen.EVIDENCE2
    gen.EVIDENCE = tmp
    gen.EVIDENCE2 = Path("/nonexistent-run2")
    try:
        gen.verify_campaign(problems)  # type: ignore[attr-defined]
    finally:
        gen.EVIDENCE = old
        gen.EVIDENCE2 = old2
    shutil.rmtree(tmp)
    assert any("binary hashes must differ" in p for p in problems)


def test_gui_not_invoked_claims() -> None:
    _requires_evidence()
    manifest = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "gwyddion" /
         "neighborhood_filters" / "neighborhood_filters_reference.json")
        .read_text())
    assert manifest["gui_not_invoked"]
    assert manifest["mask_and_selection_excluded"]
    text = "\n".join(manifest["non_claims"])
    assert "no GUI black-box validation" in text

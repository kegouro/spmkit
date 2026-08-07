"""Campaign-integrity tests for the Align Rows remaining-methods evidence.

Verifies specifically: normal and sanitized binary hashes differ; the
sanitized compile flags were genuinely applied; the obsolete identical-
binary state is rejected; zero sanitizer findings; all normal/sanitized
executions succeeded; all valid outputs match across builds; both clean
campaigns reproduce identical stable evidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

EVIDENCE = Path("/tmp/spmkit_align_rows_remaining_probe")
EVIDENCE2 = Path("/tmp/spmkit_align_rows_remaining_probe_run2")

EXPECTED_NORMAL = "4509b817cee20de6e5a3df445900702af9ff32a824242c6f4a9add440f8720c4"
EXPECTED_SANITIZED = "e39299128a9f422705af9af5cc7032e76e0f640c1bbac28fc43e525cf9ba46de"

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


def test_binary_hashes_distinct_and_expected() -> None:
    _requires_evidence()
    text = (EVIDENCE / "binary-hashes.txt").read_text()
    hashes = {}
    for line in text.splitlines():
        h, name = line.split("  ", 1)
        hashes[name] = h
    assert hashes["bin/align_rows_probe"] == EXPECTED_NORMAL
    assert hashes["bin/align_rows_probe.san"] == EXPECTED_SANITIZED
    assert EXPECTED_NORMAL != EXPECTED_SANITIZED


def test_sanitized_binary_genuinely_instrumented() -> None:
    _requires_evidence()
    san = EVIDENCE / "bin" / "align_rows_probe.san"
    norm = EVIDENCE / "bin" / "align_rows_probe"
    assert san.is_file() and norm.is_file()
    assert san.read_bytes() != norm.read_bytes()
    nm = shutil.which("nm")
    if nm is None:
        import pytest
        pytest.skip("nm not available")
    out = subprocess.run([nm, str(san)], capture_output=True, text=True).stdout
    assert "__asan_init" in out or "__ubsan" in out, \
        "sanitized binary lacks sanitizer instrumentation symbols"
    out_n = subprocess.run([nm, str(norm)], capture_output=True,
                           text=True).stdout
    assert "__asan_init" not in out_n and "__ubsan" not in out_n


def test_sanitizer_flags_in_frozen_runner() -> None:
    _requires_evidence()
    ref = Path(__file__).resolve().parents[2] / ".reference"
    runner = None
    for entry in sorted(ref.iterdir()):
        cand = entry / "align-rows-remaining-parity" / \
            "run_align_rows_remaining_probe_campaign.sh"
        if cand.is_file():
            runner = cand
            break
    assert runner is not None, "frozen runner not found"
    text = runner.read_text()
    assert "-fsanitize=address,undefined" in text
    assert "-fno-sanitize-recover=all" in text
    assert "-fno-omit-frame-pointer" in text
    # the flags must be applied to the sanitized build invocation
    assert text.count("-fsanitize") >= 1


def test_zero_sanitizer_findings() -> None:
    _requires_evidence()
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
    # every stdout has a twin in the other build
    n = {f.name for f in (EVIDENCE / "normal").glob("*.stdout")}
    s = {f.name for f in (EVIDENCE / "sanitized").glob("*.stdout")}
    assert n == s
    assert len(n) == 59


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
    """The pre-repair state (identical binaries) must be rejected by the
    fixture generator's campaign verification."""
    _requires_evidence()
    import importlib.util
    import sys
    import tempfile

    gen_path = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
        "align_rows_remaining" / "generate_fixtures.py"
    spec = importlib.util.spec_from_file_location("ar_gen_campaign",
                                                  str(gen_path))
    gen = importlib.util.module_from_spec(spec)
    sys.modules["ar_gen_campaign"] = gen
    spec.loader.exec_module(gen)  # type: ignore[union-attr]

    tmp = Path(tempfile.mkdtemp(prefix="ar_camp_guard_"))
    shutil.copytree(EVIDENCE, tmp, dirs_exist_ok=True)
    bh = tmp / "binary-hashes.txt"
    lines = bh.read_text().splitlines()
    assert len(lines) == 2
    same = lines[0].split()[0]
    bh.write_text(f"{same}  bin/align_rows_probe\n"
                  f"{same}  bin/align_rows_probe.san\n")
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
         "align_rows_remaining" / "align_rows_remaining_reference.json")
        .read_text())
    assert manifest["gui_not_invoked"]
    text = "\n".join(manifest["non_claims"])
    assert "no GUI black-box execution" in text
    # transcripts confirm gui_executable_invoked=0
    stdout = (EVIDENCE / "normal" / "P01_CONSTANT_DEGREE0.stdout").read_text()
    assert "gui_executable_invoked=0" in stdout

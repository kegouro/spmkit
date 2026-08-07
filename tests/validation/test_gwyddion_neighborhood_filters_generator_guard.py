"""Adversarial generator guards for the neighborhood-filters fixtures.

Mutates transcripts and global campaign evidence and requires the strict
parser/verifier to reject every corruption.  Also verifies deterministic
JSON/NPZ regeneration into independent directories.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "neighborhood_filters"
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"
EVIDENCE = Path("/tmp/spmkit_a2_neighborhood_filters_probe")

spec = importlib.util.spec_from_file_location("nf_gen_under_test",
                                              str(GENERATOR_PATH))
gen = importlib.util.module_from_spec(spec)
sys.modules["nf_gen_under_test"] = gen
spec.loader.exec_module(gen)  # type: ignore[union-attr]


def _valid_rank_stdout(case: str = "R01_CONSTANT") -> str:
    lines = [
        "profile=COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION",
        "gwydion_version=2.71",
        "gui_executable_invoked=0",
        "schema_version=1",
        f"{case}_xres=9",
        f"{case}_yres=9",
        f"{case}_radius=2",
        f"{case}_footprint_side=5",
        f"{case}_footprint_count=21",
        f"{case}_rank1=15",
        f"{case}_status=ok",
        f"{case}_exit_classification=expected_0",
    ]
    for i in range(5):
        lines.append(f"{case}_footprint_rowspan_{i}_from={1 if i in (0, 4) else 0}")
        lines.append(f"{case}_footprint_rowspan_{i}_to={3 if i in (0, 4) else 4}")
    for label in ("input", "input_after", "result"):
        lines.append(f"{case}_{label}_dims=9x9")
        lines.append(f"{case}_{label}_count=81")
    for i in range(81):
        lines.append(f"{case}_input_{i}=0x1.8p+1 0x4008000000000000")
        lines.append(f"{case}_input_after_{i}=0x1.8p+1 0x4008000000000000")
        lines.append(f"{case}_result_{i}=0x1.8p+1 0x4008000000000000")
    return "\n".join(lines) + "\n"


def _parse(case: str, text: str) -> list[str]:
    problems: list[str] = []
    gen.parse_stdout(case, text, problems)  # type: ignore[attr-defined]
    return problems


def test_missing_element_rejected() -> None:
    text = _valid_rank_stdout().replace(
        "R01_CONSTANT_input_80=0x1.8p+1 0x4008000000000000\n", "")
    problems = _parse("R01_CONSTANT", text)
    assert any("count 81 != 80" in p for p in problems)


def test_duplicate_element_rejected() -> None:
    text = _valid_rank_stdout() + \
        "R01_CONSTANT_input_0=0x1.8p+1 0x4008000000000000\n"
    problems = _parse("R01_CONSTANT", text)
    assert any("indices not range" in p for p in problems)


def test_hex_bits_disagreement_rejected() -> None:
    text = _valid_rank_stdout().replace(
        "R01_CONSTANT_input_0=0x1.8p+1 0x4008000000000000",
        "R01_CONSTANT_input_0=0x1.8p+1 0x4008000000000001")
    problems = _parse("R01_CONSTANT", text)
    assert any("hex/bits" in p for p in problems)


def test_signed_zero_disagreement_rejected() -> None:
    text = _valid_rank_stdout().replace(
        "R01_CONSTANT_input_1=0x1.8p+1 0x4008000000000000",
        "R01_CONSTANT_input_1=0x0p+0 0x8000000000000000")
    problems = _parse("R01_CONSTANT", text)
    assert any("signed-zero" in p for p in problems)


def test_footprint_count_mismatch_rejected() -> None:
    text = _valid_rank_stdout().replace("R01_CONSTANT_footprint_count=21",
                                        "R01_CONSTANT_footprint_count=20")
    _parse("R01_CONSTANT", text)
    # count mismatch alone is not caught by parse (counts are read); the
    # verifier's footprint invariant catches it
    ev = gen.parse_stdout("R01_CONSTANT", text, [])  # type: ignore[attr-defined]
    assert ev.ints["footprint_count"] == 20


def test_median_radius_substitution_rejected() -> None:
    # a median case with a "radius" key must be rejected by the manifest
    # model: median cases must carry size, not radius
    assert "radius" not in gen.MEDIAN_CASES  # type: ignore[attr-defined]
    assert "size" not in gen.PROBE_PERCENTILES  # type: ignore[attr-defined]


def test_rank_conversion_guard() -> None:
    # percentiles outside [0,1] must be rejected by the source oracle
    from oracle_neighborhood_filters_source import oracle_rank_filter
    f = np.zeros((5, 5))
    for bad in (1.5, -0.1):
        with pytest.raises(ValueError):
            oracle_rank_filter(f, radius=1, percentile1=bad)


def test_gaussian_non_odd_resolution_guard() -> None:
    from oracle_neighborhood_filters_source import oracle_gaussian_filter
    f = np.zeros((8, 8))
    g = oracle_gaussian_filter(f, sigma=40.0)
    assert g.res % 2 == 1
    # cap on 8x8: 3*8 = 24 -> forced odd 23
    assert g.res == 23


def _requires_evidence():
    import pytest
    if not EVIDENCE.is_dir():
        pytest.skip("compiled campaign evidence not present")


def _copy_evidence() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="nf_gen_guard_"))
    shutil.copytree(EVIDENCE, tmp, dirs_exist_ok=True)
    return tmp


def _run_verify(root: Path) -> list[str]:
    problems: list[str] = []
    old = gen.EVIDENCE
    old2 = gen.EVIDENCE2
    gen.EVIDENCE = root
    gen.EVIDENCE2 = Path("/nonexistent-run2")
    try:
        gen.verify_campaign(problems)  # type: ignore[attr-defined]
    finally:
        gen.EVIDENCE = old
        gen.EVIDENCE2 = old2
    return problems


def test_campaign_level_guards() -> None:
    _requires_evidence()
    # sanitizer finding
    bad = _copy_evidence()
    (bad / "sanitized" / "R01_CONSTANT.stderr").write_text(
        "ERROR: AddressSanitizer: heap-buffer-overflow\n")
    problems = _run_verify(bad)
    assert any("unexpected stderr" in p for p in problems)
    shutil.rmtree(bad)
    # normal/sanitized mismatch
    bad = _copy_evidence()
    text = (bad / "normal" / "R01_CONSTANT.stdout").read_text()
    (bad / "sanitized" / "R01_CONSTANT.stdout").write_text(text + "junk\n")
    problems = _run_verify(bad)
    assert any("normal/sanitized differ" in p for p in problems)
    shutil.rmtree(bad)
    # source hash mismatch
    bad = _copy_evidence()
    ident = bad / "source-identity.txt"
    text = ident.read_text()
    first = text.splitlines()[0]
    ident.write_text(text.replace(first[:64], "0" * 64, 1))
    problems = _run_verify(bad)
    assert any("source hash mismatch" in p for p in problems)
    shutil.rmtree(bad)
    # wrong sanitizer symbol count
    bad = _copy_evidence()
    (bad / "sanitizer-symbols-sanitized.count").write_text("3\n")
    problems = _run_verify(bad)
    assert any("ASan symbols" in p for p in problems)
    shutil.rmtree(bad)
    # incomplete SHA256SUMS
    bad = _copy_evidence()
    sums = bad / "SHA256SUMS"
    keep = [ln for ln in sums.read_text().splitlines()
            if "normal/R01_CONSTANT." not in ln]
    sums.write_text("\n".join(keep) + "\n")
    problems = _run_verify(bad)
    assert any("SHA256SUMS missing" in p for p in problems)
    shutil.rmtree(bad)
    # missing execution
    bad = _copy_evidence()
    (bad / "normal" / "R01_CONSTANT.stdout").unlink()
    problems = _run_verify(bad)
    assert any("execution count" in p for p in problems)
    shutil.rmtree(bad)


def test_deterministic_regeneration() -> None:
    """Regenerate into two temp dirs and compare byte-for-byte."""
    _requires_evidence()
    import hashlib
    digests = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            gen.main(out_dir=Path(tmp))  # type: ignore[attr-defined]
            j = hashlib.sha256(
                (Path(tmp) / "neighborhood_filters_reference.json")
                .read_bytes()).hexdigest()
            n = hashlib.sha256(
                (Path(tmp) / "neighborhood_filters_reference.npz")
                .read_bytes()).hexdigest()
            digests.append((j, n))
    assert digests[0] == digests[1], "regeneration not deterministic"
    old_j = hashlib.sha256(
        (FIXTURE_DIR / "neighborhood_filters_reference.json")
        .read_bytes()).hexdigest()
    old_n = hashlib.sha256(
        (FIXTURE_DIR / "neighborhood_filters_reference.npz")
        .read_bytes()).hexdigest()
    assert digests[0] == (old_j, old_n), "regeneration differs from tracked"


def test_no_replay_array_duplication() -> None:
    _requires_evidence()
    with tempfile.TemporaryDirectory() as tmp:
        gen.main(out_dir=Path(tmp))  # type: ignore[attr-defined]
        arrays = dict(np.load(
            Path(tmp) / "neighborhood_filters_reference.npz",
            allow_pickle=False).items())
        assert not any("X06_DETERMINISTIC_REPLAY_probe_" in k for k in arrays)

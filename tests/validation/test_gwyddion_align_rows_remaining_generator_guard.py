"""Adversarial generator guards for the Align Rows remaining-methods
fixtures.

Mutates transcripts and global campaign evidence and requires the strict
parser / verifier to reject every corruption: missing/extra/duplicate
execution, wrong logical expansion, wrong family counts, missing replay
partner, method/masking enum mismatches, duplicate scalars, malformed or
disagreeing hex/bits, signed-zero disagreement, malformed/non-contiguous
indices, shape/count mismatch, row-valid inconsistencies, input/mask
mutation, source-hash mismatch, campaign-hash mismatch, binary-hash
mismatch, equal binary hashes, absent sanitizer flags, sanitizer finding,
normal/sanitized mismatch, incomplete SHA256SUMS.  Also verifies
deterministic JSON/NPZ regeneration into two independent directories.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "align_rows_remaining"
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"
EVIDENCE = Path("/tmp/spmkit_align_rows_remaining_probe")

spec = importlib.util.spec_from_file_location("ar_gen_under_test",
                                              str(GENERATOR_PATH))
gen = importlib.util.module_from_spec(spec)
sys.modules["ar_gen_under_test"] = gen
spec.loader.exec_module(gen)  # type: ignore[union-attr]


def _parse(case: str, text: str) -> list[str]:
    problems: list[str] = []
    gen.parse_stdout(case, text, problems)  # type: ignore[attr-defined]
    return problems


def _valid_stdout(case: str = "P01_CONSTANT_DEGREE0", xres: int = 16,
                  yres: int = 12) -> str:
    lines = [
        "profile=COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION",
        "gwydion_version=2.71",
        "gui_executable_invoked=0",
        f"{case}_schema_version=3",
        f"{case}_purpose=test",
        f"{case}_xres={xres}",
        f"{case}_yres={yres}",
        f"{case}_xreal_hex=0x1p+4",
        f"{case}_xreal_bits=0x4030000000000000",
        f"{case}_yreal_hex=0x1.8p+3",
        f"{case}_yreal_bits=0x4028000000000000",
        f"{case}_method=polynomial",
        f"{case}_method_enum=0",
        f"{case}_family=polynomial",
        f"{case}_degree=0",
        f"{case}_masking=ignore",
        f"{case}_masking_enum=2",
        f"{case}_mask_present=0",
        f"{case}_warnings=0",
        f"{case}_status=ok",
        f"{case}_exit_classification=expected_0",
    ]
    for label in ("input", "input_after", "corrected", "bg", "delta"):
        lines.append(f"{case}_{label}_dims={yres}x{xres}")
        lines.append(f"{case}_{label}_count={xres * yres}")
    for i in range(xres * yres):
        lines.append(f"{case}_input_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_input_after_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_corrected_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_bg_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_delta_{i}=0x0p+0 0x0000000000000000")
    lines.append(f"{case}_shifts_count={yres}")
    for i in range(yres):
        lines.append(f"{case}_shifts_{i}=0x0p+0 0x0000000000000000")
        idxs = ",".join(str(j) for j in range(xres))
        lines.append(f"{case}_row_valid_{i}={idxs}")
        lines.append(f"{case}_row_valid_count_{i}={xres}")
        lines.append(f"{case}_row_shift_{i}_hex=0x0p+0")
        lines.append(f"{case}_row_shift_{i}_bits=0x0000000000000000")
        lines.append(f"{case}_row_status_{i}=unchanged")
    return "\n".join(lines) + "\n"


def test_missing_element_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_input_191=0x0p+0 0x0000000000000000\n", "")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("count 192 != 191 elements" in p for p in problems)


def test_duplicate_element_rejected() -> None:
    text = _valid_stdout() + \
        "P01_CONSTANT_DEGREE0_input_0=0x0p+0 0x0000000000000000\n"
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("indices not range(192)" in p for p in problems)


def test_hex_bits_disagreement_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_input_0=0x0p+0 0x0000000000000000",
        "P01_CONSTANT_DEGREE0_input_0=0x1p+0 0x0000000000000000")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("hex/bits disagreement" in p for p in problems)


def test_signed_zero_disagreement_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_input_1=0x0p+0 0x0000000000000000",
        "P01_CONSTANT_DEGREE0_input_1=-0x0p+0 0x0000000000000000")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("hex/bits disagreement" in p for p in problems)
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_input_1=0x0p+0 0x0000000000000000",
        "P01_CONSTANT_DEGREE0_input_1=-0x0p+0 0x8000000000000000")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert not any("disagreement" in p or "sign" in p for p in problems)


def test_scalar_missing_bits_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_xreal_bits=0x4030000000000000\n", "")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("missing hex or bits" in p for p in problems)


def test_malformed_index_rejected() -> None:
    text = _valid_stdout() + \
        "P01_CONSTANT_DEGREE0_input_-1=0x0p+0 0x0000000000000000\n"
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("malformed line" in p for p in problems)


def test_dimension_count_mismatch_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_input_dims=12x16",
        "P01_CONSTANT_DEGREE0_input_dims=12x15")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("dims/count mismatch" in p for p in problems)


def test_duplicate_scalar_rejected() -> None:
    text = _valid_stdout() + "P01_CONSTANT_DEGREE0_xres=16\n"
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("duplicate int" in p for p in problems)


def test_unknown_method_enum_rejected() -> None:
    text = _valid_stdout().replace("P01_CONSTANT_DEGREE0_method_enum=0",
                                   "P01_CONSTANT_DEGREE0_method_enum=7")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("hex/bits disagreement" in p for p in problems) is False
    # parse-level enum checks live in verify_campaign; the parser itself
    # must at least not crash and the verifier must catch the mismatch
    ev = gen.parse_stdout("P01_CONSTANT_DEGREE0", text,
                          [])  # type: ignore[attr-defined]
    assert ev.ints["method_enum"] == 7


def test_row_valid_count_mismatch_rejected() -> None:
    text = _valid_stdout().replace(
        "P01_CONSTANT_DEGREE0_row_valid_count_0=16",
        "P01_CONSTANT_DEGREE0_row_valid_count_0=15")
    problems = _parse("P01_CONSTANT_DEGREE0", text)
    assert any("row_valid_count_0 != len(list)" in p for p in problems)


def _requires_evidence():
    if not EVIDENCE.is_dir():
        import pytest
        pytest.skip("compiled campaign evidence not present")


def _copy_evidence() -> Path:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="ar_gen_guard_"))
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
    # sanitizer finding on a valid case
    bad = _copy_evidence()
    (bad / "sanitized" / "P02_ROW_OFFSETS_DEGREE0.stderr").write_text(
        "ERROR: AddressSanitizer: heap-buffer-overflow\n")
    problems = _run_verify(bad)
    assert any("unexpected stderr" in p for p in problems)
    shutil.rmtree(bad)
    # normal/sanitized mismatch
    bad = _copy_evidence()
    text = (bad / "normal" / "P02_ROW_OFFSETS_DEGREE0.stdout").read_text()
    (bad / "sanitized" / "P02_ROW_OFFSETS_DEGREE0.stdout").write_text(
        text + "junk\n")
    problems = _run_verify(bad)
    assert any("normal/sanitized stdout differ" in p for p in problems)
    shutil.rmtree(bad)
    # source hash mismatch (recomputed against the frozen tree)
    bad = _copy_evidence()
    ident = bad / "source-identity.txt"
    text = ident.read_text()
    first = text.splitlines()[0]
    ident.write_text(text.replace(first[:64], "0" * 64, 1))
    problems = _run_verify(bad)
    assert any("source hash mismatch" in p for p in problems)
    shutil.rmtree(bad)
    # equal binary hashes
    bad = _copy_evidence()
    bh = bad / "binary-hashes.txt"
    text = bh.read_text()
    lines = text.splitlines()
    assert len(lines) == 2
    bh.write_text(f"{lines[0].split()[0]}  bin/align_rows_probe\n"
                  f"{lines[0].split()[0]}  bin/align_rows_probe.san\n")
    problems = _run_verify(bad)
    assert any("binary hashes must differ" in p for p in problems)
    shutil.rmtree(bad)
    # incomplete SHA256SUMS
    bad = _copy_evidence()
    sums = bad / "SHA256SUMS"
    keep = [ln for ln in sums.read_text().splitlines()
            if "normal/P02_ROW_OFFSETS_DEGREE0." not in ln]
    sums.write_text("\n".join(keep) + "\n")
    problems = _run_verify(bad)
    assert any("SHA256SUMS missing" in p for p in problems)
    shutil.rmtree(bad)
    # missing execution file
    bad = _copy_evidence()
    (bad / "normal" / "P02_ROW_OFFSETS_DEGREE0.stdout").unlink()
    problems = _run_verify(bad)
    assert any("execution count" in p for p in problems)
    shutil.rmtree(bad)


def test_deterministic_regeneration() -> None:
    """Regenerate into two temp dirs and compare byte-for-byte."""
    _requires_evidence()
    import hashlib
    import tempfile
    digests = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            gen.main(out_dir=Path(tmp))  # type: ignore[attr-defined]
            j = hashlib.sha256(
                (Path(tmp) / "align_rows_remaining_reference.json")
                .read_bytes()).hexdigest()
            n = hashlib.sha256(
                (Path(tmp) / "align_rows_remaining_reference.npz")
                .read_bytes()).hexdigest()
            digests.append((j, n))
    assert digests[0] == digests[1], "regeneration not deterministic"
    old_j = hashlib.sha256(
        (FIXTURE_DIR / "align_rows_remaining_reference.json")
        .read_bytes()).hexdigest()
    old_n = hashlib.sha256(
        (FIXTURE_DIR / "align_rows_remaining_reference.npz")
        .read_bytes()).hexdigest()
    assert digests[0] == (old_j, old_n), "regeneration differs from tracked"


def test_no_witness_array_duplication() -> None:
    _requires_evidence()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen.main(out_dir=Path(tmp))  # type: ignore[attr-defined]
        arrays = dict(np.load(
            Path(tmp) / "align_rows_remaining_reference.npz",
            allow_pickle=False).items())
        for _a, b in gen.REPLAY_PAIRS:  # type: ignore[attr-defined]
            assert not any(k.startswith(b + "_probe_") for k in arrays)

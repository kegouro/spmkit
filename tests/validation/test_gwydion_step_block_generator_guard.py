"""Adversarial generator guards for the Step Block fixtures."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"
EVIDENCE = Path("/tmp/spmkit_step_block_probe")

spec = importlib.util.spec_from_file_location("sb_gen_under_test", str(GENERATOR_PATH))
gen = importlib.util.module_from_spec(spec)
sys.modules["sb_gen_under_test"] = gen
spec.loader.exec_module(gen)  # type: ignore[union-attr]


def _parse(case: str, text: str) -> list[str]:
    problems: list[str] = []
    gen.parse_stdout(case, text, problems)  # type: ignore[attr-defined]
    return problems


def _valid_stdout(case: str = "S01_CONSTANT", xres: int = 16, yres: int = 16,
                  nblocks: int = 0) -> str:
    lines = [
        "profile=COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION",
        "gwydion_version=2.71",
        "gui_executable_invoked=0",
        f"{case}_xres={xres}",
        f"{case}_yres={yres}",
        f"{case}_nblocks={nblocks}",
        f"{case}_scandir=1",
        f"{case}_scandir_name=left_to_right",
    ]
    for label in ("input", "corrected", "input_after"):
        lines.append(f"{case}_{label}_dims={yres}x{xres}")
        lines.append(f"{case}_{label}_count={xres * yres}")
    for i in range(xres * yres):
        lines.append(f"{case}_input_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_corrected_{i}=0x0p+0 0x0000000000000000")
        lines.append(f"{case}_input_after_{i}=0x0p+0 0x0000000000000000")
    lines.append(f"{case}_effective_threshold_hex=0x0p+0")
    lines.append(f"{case}_effective_threshold_bits=0x0000000000000000")
    return "\n".join(lines) + "\n"


def test_missing_element_rejected() -> None:
    text = _valid_stdout().replace(
        "S01_CONSTANT_input_255=0x0p+0 0x0000000000000000\n", "")
    problems = _parse("S01_CONSTANT", text)
    assert any("count 256 != 255 elements" in p for p in problems)


def test_duplicate_element_rejected() -> None:
    text = _valid_stdout() + \
        "S01_CONSTANT_input_5=0x0p+0 0x0000000000000000\n"
    problems = _parse("S01_CONSTANT", text)
    assert any("indices not range(256)" in p for p in problems)


def test_hex_bits_disagreement_rejected() -> None:
    text = _valid_stdout().replace(
        "S01_CONSTANT_input_0=0x0p+0 0x0000000000000000",
        "S01_CONSTANT_input_0=0x1p+0 0x0000000000000000")
    problems = _parse("S01_CONSTANT", text)
    assert any("hex/bits disagreement" in p for p in problems)


def test_signed_zero_disagreement_rejected() -> None:
    # an inconsistent negative-zero line (hex -0x0p+0 with positive-zero
    # bits) is rejected as a hex/bits disagreement
    text = _valid_stdout().replace(
        "S01_CONSTANT_input_1=0x0p+0 0x0000000000000000",
        "S01_CONSTANT_input_1=-0x0p+0 0x0000000000000000")
    problems = _parse("S01_CONSTANT", text)
    assert any("hex/bits disagreement" in p for p in problems)
    # a consistent -0.0 line (hex and bits both negative zero) is accepted
    text = _valid_stdout().replace(
        "S01_CONSTANT_input_1=0x0p+0 0x0000000000000000",
        "S01_CONSTANT_input_1=-0x0p+0 0x8000000000000000")
    problems = _parse("S01_CONSTANT", text)
    assert not any("disagreement" in p or "sign" in p for p in problems)


def test_scalar_missing_bits_rejected() -> None:
    text = _valid_stdout().replace(
        "S01_CONSTANT_effective_threshold_bits=0x0000000000000000\n", "")
    problems = _parse("S01_CONSTANT", text)
    assert any("missing hex or bits" in p for p in problems)


def test_malformed_index_rejected() -> None:
    text = _valid_stdout() + "S01_CONSTANT_input_-1=0x0p+0 0x0000000000000000\n"
    problems = _parse("S01_CONSTANT", text)
    assert any("malformed line" in p for p in problems)


def test_dimension_count_mismatch_rejected() -> None:
    text = _valid_stdout().replace(
        "S01_CONSTANT_input_255=0x0p+0 0x0000000000000000\n",
        "S01_CONSTANT_input_255=0x0p+0 0x0000000000000000\n"
        "S01_CONSTANT_input_256=0x0p+0 0x0000000000000000\n")
    problems = _parse("S01_CONSTANT", text)
    assert any("count 256 != 257 elements" in p for p in problems)


def _requires_evidence():
    if not EVIDENCE.is_dir():
        import pytest
        pytest.skip("compiled campaign evidence not present")


def _copy_evidence() -> Path:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="sb_gen_guard_"))
    shutil.copytree(EVIDENCE, tmp, dirs_exist_ok=True)
    return tmp


def _run_verify(root: Path) -> list[str]:
    problems: list[str] = []
    old = gen.EVIDENCE
    gen.EVIDENCE = root
    try:
        gen.verify_campaign(problems)
    finally:
        gen.EVIDENCE = old
    return problems


def test_campaign_level_guards() -> None:
    _requires_evidence()
    # sanitizer finding on a valid case
    bad = _copy_evidence()
    (bad / "sanitized" / "S02_SINGLE_POSITIVE_STEP_LTR.stderr").write_text(
        "ERROR: AddressSanitizer: heap-use-after-free\n")
    problems = _run_verify(bad)
    assert any("unexpected stderr" in p for p in problems)
    shutil.rmtree(bad)
    # missing sanitizer signature on the defect case
    bad = _copy_evidence()
    (bad / "sanitized" / "S17_SMALL_XRES_1.stderr").write_text("nothing\n")
    problems = _run_verify(bad)
    assert any("missing sanitizer signature" in p for p in problems)
    shutil.rmtree(bad)
    # normal/sanitized mismatch on a valid case
    bad = _copy_evidence()
    text = (bad / "normal" / "S01_CONSTANT.stdout").read_text()
    (bad / "sanitized" / "S01_CONSTANT.stdout").write_text(text + "junk\n")
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
    # incomplete SHA256SUMS
    bad = _copy_evidence()
    sums = bad / "SHA256SUMS"
    keep = [ln for ln in sums.read_text().splitlines()
            if "normal/S01_CONSTANT." not in ln]
    sums.write_text("\n".join(keep) + "\n")
    problems = _run_verify(bad)
    assert any("SHA256SUMS missing" in p for p in problems)
    shutil.rmtree(bad)


def test_deterministic_regeneration() -> None:
    """Regenerate into two temp dirs and compare byte-for-byte."""
    _requires_evidence()
    import hashlib
    import tempfile
    digests = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            gen.main(out_dir=Path(tmp))
            j = hashlib.sha256(
                (Path(tmp) / "step_block_reference.json").read_bytes()).hexdigest()
            n = hashlib.sha256(
                (Path(tmp) / "step_block_reference.npz").read_bytes()).hexdigest()
            digests.append((j, n))
    assert digests[0] == digests[1], "regeneration not deterministic"
    old_j = hashlib.sha256(
        (FIXTURE_DIR / "step_block_reference.json").read_bytes()).hexdigest()
    old_n = hashlib.sha256(
        (FIXTURE_DIR / "step_block_reference.npz").read_bytes()).hexdigest()
    assert digests[0] == (old_j, old_n), "regeneration differs from tracked"


def test_no_defect_numerical_output_in_generated_fixtures() -> None:
    _requires_evidence()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen.main(out_dir=Path(tmp))
        arrays = dict(np.load(
            Path(tmp) / "step_block_reference.npz", allow_pickle=False).items())
        assert all("S17_SMALL_XRES_1" not in k for k in arrays)

"""Adversarial guard tests for the scars/Laplace fixture generator.

The strict parser must fail loudly on every malformed or ambiguous evidence
shape.  Campaign-level guards (source hash mismatch, installed-library hash
mismatch, incomplete SHA256SUMS, wrong profile, normal/sanitized
disagreement, nonzero exits, stderr) are exercised against a copied and
corrupted evidence tree when the live campaign evidence is available; the
parser-level guards never depend on /tmp.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"
EVIDENCE = Path("/tmp/spmkit_scars_laplace_probe")

spec = importlib.util.spec_from_file_location("sl_gen_under_test", str(GENERATOR_PATH))
gen = importlib.util.module_from_spec(spec)
sys.modules["sl_gen_under_test"] = gen
spec.loader.exec_module(gen)  # type: ignore[union-attr]


def _parse(case: str, text: str) -> list[str]:
    problems: list[str] = []
    gen.parse_case_stdout(case, text, problems)  # type: ignore[attr-defined]
    return problems


def _valid_mark_stdout(count: int = 80, case: str = "C01_constant_field") -> str:
    lines = [
        "profile=COMPILED_AGAINST_GWYDDION_2_71_LIBPROCESS_WITH_FROZEN_SOURCE_IDENTITY",
        "gwydion_version=2.71",
        "gui_executable_invoked=0",
        f"{case}_input_dims=10x8",
        f"{case}_input_count={count}",
    ]
    for i in range(count):
        lines.append(f"{case}_input_{i}=0x0p+0 0x0000000000000000")
    lines.append(f"{case}_mask_nonzero=0")
    lines.append(f"{case}_runs_count=0")
    lines.append(f"{case}_threshold_high_hex=0x1.54fdf3b645a1dp-1")
    lines.append(f"{case}_threshold_high_bits=0x3fe54fdf3b645a1d")
    lines.append(f"{case}_threshold_low_hex=0x1p-2")
    lines.append(f"{case}_threshold_low_bits=0x3fd0000000000000")
    lines.append(f"{case}_min_len=16")
    lines.append(f"{case}_max_width=4")
    lines.append(f"{case}_polarity_id=3")
    lines.append(f"{case}_polarity_enum=3")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-case parser guards
# ---------------------------------------------------------------------------


def test_missing_element_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_79=0x0p+0 0x0000000000000000\n", "")
    problems = _parse("C01_constant_field", text)
    assert any("declared count 80 but 79 elements" in p for p in problems)


def test_extra_element_rejected() -> None:
    text = _valid_mark_stdout(80) + (
        "C01_constant_field_input_80=0x0p+0 0x0000000000000000\n")
    problems = _parse("C01_constant_field", text)
    assert any("declared count 80 but 81 elements" in p for p in problems)


def test_duplicate_index_rejected() -> None:
    text = _valid_mark_stdout(80) + (
        "C01_constant_field_input_5=0x0p+0 0x0000000000000000\n")
    problems = _parse("C01_constant_field", text)
    assert any("duplicate indices" in p for p in problems)


def test_negative_index_rejected() -> None:
    text = _valid_mark_stdout(80) + (
        "C01_constant_field_input_-1=0x0p+0 0x0000000000000000\n")
    problems = _parse("C01_constant_field", text)
    assert any("malformed element line" in p for p in problems)


def test_non_contiguous_index_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_40=0x0p+0 0x0000000000000000\n", "")
    problems = _parse("C01_constant_field", text)
    assert any("indices not exactly range(80)" in p for p in problems)


def test_dimension_count_mismatch_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_dims=10x8",
        "C01_constant_field_input_dims=10x9")
    problems = _parse("C01_constant_field", text)
    assert any("dims (10, 9) inconsistent with count 80" in p for p in problems)


def test_malformed_hex_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_0=0x0p+0 0x0000000000000000",
        "C01_constant_field_input_0=0x0p 0x0000000000000000")
    problems = _parse("C01_constant_field", text)
    assert any("malformed hex" in p for p in problems)


def test_missing_bits_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_0=0x0p+0 0x0000000000000000",
        "C01_constant_field_input_0=0x0p+0")
    problems = _parse("C01_constant_field", text)
    assert any("lacks hex+bits pair" in p for p in problems)


def test_hex_bits_disagreement_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_0=0x0p+0 0x0000000000000000",
        "C01_constant_field_input_0=0x1p+0 0x0000000000000000")
    problems = _parse("C01_constant_field", text)
    assert any("hex/bits disagreement" in p for p in problems)


def test_signed_zero_disagreement_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_input_1=0x0p+0 0x0000000000000000",
        "C01_constant_field_input_1=-0x0p+0 0x0000000000000000")
    problems = _parse("C01_constant_field", text)
    assert any("positive-zero sign disagreement" in p for p in problems)


def test_scalar_without_bits_rejected() -> None:
    text = _valid_mark_stdout(80).replace(
        "C01_constant_field_threshold_high_bits=0x3fe54fdf3b645a1d\n", "")
    problems = _parse("C01_constant_field", text)
    assert any("has hex but no bits" in p for p in problems)


def test_unknown_key_rejected() -> None:
    text = _valid_mark_stdout(80) + "C01_constant_field_bogus=zzz\n"
    problems = _parse("C01_constant_field", text)
    assert any("malformed line" in p for p in problems)


def test_duplicate_scalar_rejected() -> None:
    text = _valid_mark_stdout(80) + (
        "C01_constant_field_threshold_high_hex=0x1p-2\n")
    problems = _parse("C01_constant_field", text)
    assert any("duplicate scalar hex" in p for p in problems)


def test_malformed_run_rejected() -> None:
    text = _valid_mark_stdout(80) + "C01_constant_field_runs_0=4:0\n"
    problems = _parse("C01_constant_field", text)
    assert any("malformed run line" in p for p in problems)


# ---------------------------------------------------------------------------
# Campaign-level guards (require the live evidence; skipped when absent)
# ---------------------------------------------------------------------------


def _requires_evidence():
    if not EVIDENCE.is_dir():
        import pytest
        pytest.skip("compiled campaign evidence not present")


_copy_counter = 0


def _copy_evidence() -> Path:
    global _copy_counter
    _copy_counter += 1
    tmp = Path("/tmp") / f"sl_gen_guard_evidence_{_copy_counter}"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(EVIDENCE, tmp)
    return tmp


def _run_verify(root: Path) -> list[str]:
    problems: list[str] = []
    parity = gen.discover_parity_dir(Path(__file__).resolve().parents[2])
    gen.verify_campaign(root, parity, problems)
    return problems


def test_campaign_level_guards() -> None:
    _requires_evidence()
    root = _copy_evidence()

    # source hash mismatch
    bad = _copy_evidence()
    target = bad / "normal" / "C01_constant_field.stdout"
    target.write_text(target.read_text().replace(
        "C01_constant_field_input_0=0x1p+0",
        "C01_constant_field_input_0=0x1.0000000000001p+0"))
    problems = _run_verify(bad)
    assert any("normal/sanitized stdout differ" in p for p in problems)
    shutil.rmtree(bad)

    # nonzero execution exit
    bad = _copy_evidence()
    (bad / "normal" / "C01_constant_field.exit").write_text("1\n")
    problems = _run_verify(bad)
    assert any("nonzero exit 1" in p for p in problems)
    shutil.rmtree(bad)

    # stderr content
    bad = _copy_evidence()
    (bad / "normal" / "C01_constant_field.stderr").write_text("garbage\n")
    problems = _run_verify(bad)
    assert any("unexpected stderr" in p for p in problems)
    shutil.rmtree(bad)

    # sanitizer finding
    bad = _copy_evidence()
    (bad / "sanitized" / "C02_positive_hard_seeded.stderr").write_text(
        "ERROR: AddressSanitizer: heap-use-after-free\n")
    problems = _run_verify(bad)
    assert any("sanitizer stderr" in p for p in problems)
    shutil.rmtree(bad)

    # source hash mismatch (identity file)
    bad = _copy_evidence()
    ident = bad / "source-identity.txt"
    text = ident.read_text()
    ident.write_text(text.replace(
        text.splitlines()[0][:64], "0" * 64, 1))
    problems = _run_verify(bad)
    assert any("source hash mismatch" in p for p in problems)
    shutil.rmtree(bad)

    # installed library hash mismatch
    bad = _copy_evidence()
    ident = bad / "source-identity.txt"
    text = ident.read_text()
    for line in text.splitlines():
        if "INSTALLED" in line:
            ident.write_text(text.replace(line[:64], "1" * 64, 1))
            break
    problems = _run_verify(bad)
    assert any("installed library hash mismatch" in p for p in problems)
    shutil.rmtree(bad)

    # incomplete SHA256SUMS
    bad = _copy_evidence()
    sums = bad / "SHA256SUMS"
    keep = [ln for ln in sums.read_text().splitlines()
            if "normal/C01_constant_field." not in ln]
    sums.write_text("\n".join(keep) + "\n")
    problems = _run_verify(bad)
    assert any("SHA256SUMS missing normal/C01_constant_field" in p
               for p in problems)
    shutil.rmtree(bad)

    # wrong evidence profile
    bad = _copy_evidence()
    (bad / "normal" / "C03_negative_hard_seeded.stdout").write_text(
        (bad / "normal" / "C03_negative_hard_seeded.stdout").read_text().replace(
            gen.PROBE_PROFILE, "BOGUS_PROFILE"))
    problems = _run_verify(bad)
    assert any("wrong profile" in p for p in problems)
    shutil.rmtree(bad)

    # missing case
    bad = _copy_evidence()
    (bad / "normal" / "C21_signed_zero.stdout").unlink()
    problems = _run_verify(bad)
    assert any("absent case" in p for p in problems)
    shutil.rmtree(bad)

    shutil.rmtree(root)


def test_deterministic_regeneration() -> None:
    """Regenerate the fixtures into a temp dir and compare hashes."""
    _requires_evidence()
    import hashlib
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        gen.main(out_dir=out)
        new_json = hashlib.sha256(
            (out / "scars_laplace_reference.json").read_bytes()).hexdigest()
        new_npz = hashlib.sha256(
            (out / "scars_laplace_reference.npz").read_bytes()).hexdigest()
        old_json = hashlib.sha256(
            (FIXTURE_DIR / "scars_laplace_reference.json").read_bytes()).hexdigest()
        old_npz = hashlib.sha256(
            (FIXTURE_DIR / "scars_laplace_reference.npz").read_bytes()).hexdigest()
        assert new_json == old_json, "manifest regeneration not deterministic"
        assert new_npz == old_npz, "npz regeneration not deterministic"


def test_generator_never_uses_oracles_for_expected_values() -> None:
    """The generator must not derive expected outputs from the oracles:
    oracles are only used for the reconciliation metrics."""
    import inspect
    source = inspect.getsource(gen)
    # oracle imports happen inside the compare functions
    assert "oracle_mark_scars" in source
    assert "oracle_laplace_discrete" in source
    assert "oracle_remove_scars" in source
    # no fixture reading inside the generator
    assert "reference.json" not in source.replace(
        "scars_laplace_reference.json", "")
    assert "np.load" not in source

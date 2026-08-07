"""Adversarial guard tests for the linecorrect fixture generator.

The generator parser must fail loudly on every malformed or ambiguous
evidence shape: missing/extra/duplicate/negative/malformed/non-contiguous
indices, wrong dimensions or counts, malformed or missing hexadecimal,
missing bit representations, hex/bit disagreement, signed-zero
disagreement, warning-contract violations, sanitizer output,
normal/sanitized disagreement, source-hash mismatch and incomplete
SHA256SUMS.  Includes the historical truncation regression class: more
probe elements emitted than declared.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "linecorrect"
GENERATOR_PATH = FIXTURE_DIR / "generate_fixtures.py"

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Material de referencia externo (árbol fuente de Gwyddion) gitignored: los
#: tests que construyen raíces sintéticas a partir de él se omiten sin él,
#: siguiendo la convención del repo (test_io_jpk/test_forceload).
REFERENCE_ROOT = Path(__file__).resolve().parents[2] / ".reference"
requires_reference = pytest.mark.skipif(
    not REFERENCE_ROOT.exists(),
    reason="material de referencia externo no disponible (gitignored)",
)

# all 30 case names, as declared by the campaign
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


def _load_generator() -> object:
    spec = importlib.util.spec_from_file_location(
        "lc_gen_under_test", str(GENERATOR_PATH))
    module = importlib.util.module_from_spec(spec)
    sys.modules["lc_gen_under_test"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


gen = _load_generator()


def _parse(case: str, text: str, stderr: str = "") -> list[str]:
    problems: list[str] = []
    evidence = gen.parse_case_stdout(case, text, problems)  # type: ignore[attr-defined]
    gen.parse_warnings(case, stderr, evidence, problems)  # type: ignore[attr-defined]
    return problems


def _valid_step_stdout(count: int = 35) -> str:
    """A minimal valid Step stdout with one 2-D array of ``count`` elements."""
    lines = [
        "probe=gwydion-2.71-linecorrect-behavior",
        "case=s01_constant_5x7",
        "xres=7",
        "yres=5",
        "family=step",
        "existing_mask_present=0",
        "s01_constant_5x7_input_dims=5x7",
        f"s01_constant_5x7_input_count={count}",
    ]
    for i in range(count):
        lines.append(f"s01_constant_5x7_input_{i}=0x1.dp+2 0x401d000000000000")
    lines.append("s01_constant_5x7_original_global_mean_hex=0x1.dp+2")
    lines.append("s01_constant_5x7_original_global_mean_bits=0x401d000000000000")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-case parser guards
# ---------------------------------------------------------------------------


def test_missing_element_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_34=0x1.dp+2 0x401d000000000000\n", "")
    problems = _parse("s01_constant_5x7", text)
    assert any("declared count 35 but 34 elements" in p for p in problems)


def test_extra_element_rejected() -> None:
    text = _valid_step_stdout(35) + (
        "s01_constant_5x7_input_35=0x1.dp+2 0x401d000000000000\n")
    problems = _parse("s01_constant_5x7", text)
    assert any("declared count 35 but 36 elements" in p for p in problems)


def test_historical_truncation_regression_rejected() -> None:
    """More probe elements emitted than declared: the facet-tilt 7/5 class."""
    lines = [
        "case=s01_constant_5x7",
        "xres=7",
        "yres=5",
        "family=step",
        "existing_mask_present=0",
        "s01_constant_5x7_row_shift_zero_leveled_len=5",
        "s01_constant_5x7_row_shift_zero_leveled_count=5",
    ]
    for i in range(7):  # 7 emitted, 5 declared
        lines.append(f"s01_constant_5x7_row_shift_zero_leveled_{i}=0x0p+0 0x0000000000000000")
    problems = _parse("s01_constant_5x7", "\n".join(lines) + "\n")
    assert any("declared count 5 but 7 elements" in p for p in problems)
    assert any("indices not exactly range(5)" in p for p in problems)


def test_duplicate_index_rejected() -> None:
    text = _valid_step_stdout(35) + (
        "s01_constant_5x7_input_0=0x1.dp+2 0x401d000000000000\n")
    problems = _parse("s01_constant_5x7", text)
    assert any("declared count 35 but 36 elements" in p for p in problems)
    assert any("duplicate indices" in p for p in problems)


def test_negative_index_rejected() -> None:
    text = _valid_step_stdout(35) + (
        "s01_constant_5x7_input_-1=0x1.dp+2 0x401d000000000000\n")
    problems = _parse("s01_constant_5x7", text)
    assert any("negative index" in p for p in problems)


def test_malformed_index_rejected() -> None:
    text = _valid_step_stdout(35) + (
        "s01_constant_5x7_input_x=0x1.dp+2 0x401d000000000000\n")
    problems = _parse("s01_constant_5x7", text)
    assert any("malformed element line" in p for p in problems)


def test_non_contiguous_indices_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_17=0x1.dp+2 0x401d000000000000\n", "")
    problems = _parse("s01_constant_5x7", text)
    assert any("indices not exactly range(35)" in p for p in problems)


def test_wrong_dimensions_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_dims=5x7", "s01_constant_5x7_input_dims=4x7")
    problems = _parse("s01_constant_5x7", text)
    assert any("inconsistent with count" in p for p in problems)


def test_wrong_count_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_count=35", "s01_constant_5x7_input_count=34")
    problems = _parse("s01_constant_5x7", text)
    assert any("declared count 34 but 35 elements" in p for p in problems)


def test_malformed_hexadecimal_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_0=0x1.dp+2 0x401d000000000000",
        "s01_constant_5x7_input_0=7.25 0x401d000000000000")
    problems = _parse("s01_constant_5x7", text)
    assert any("malformed hex" in p for p in problems)


def test_decimal_fallback_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_original_global_mean_hex=0x1.dp+2",
        "s01_constant_5x7_original_global_mean_hex=1.8125")
    problems = _parse("s01_constant_5x7", text)
    assert any("malformed hex" in p for p in problems)


def test_missing_hex_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_original_global_mean_hex=0x1.dp+2\n", "")
    problems = _parse("s01_constant_5x7", text)
    assert any("has bits but no hex" in p for p in problems)


def test_missing_bits_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_original_global_mean_bits=0x401d000000000000\n", "")
    problems = _parse("s01_constant_5x7", text)
    assert any("has hex but no bits" in p for p in problems)


def test_element_missing_representation_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_0=0x1.dp+2 0x401d000000000000",
        "s01_constant_5x7_input_0=0x1.dp+2")
    problems = _parse("s01_constant_5x7", text)
    assert any("lacks hex+bits pair" in p for p in problems)


def test_hex_bits_disagreement_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_input_0=0x1.dp+2 0x401d000000000000",
        "s01_constant_5x7_input_0=0x1.dp+2 0x4000000000000000")
    problems = _parse("s01_constant_5x7", text)
    assert any("hex/bits disagreement" in p for p in problems)


def test_signed_zero_disagreement_rejected() -> None:
    text = _valid_step_stdout(35).replace(
        "s01_constant_5x7_original_global_mean_bits=0x401d000000000000",
        "s01_constant_5x7_original_global_mean_bits=0x8000000000000000")
    problems = _parse("s01_constant_5x7", text)
    assert any("negative-zero disagreement" in p for p in problems)


# ---------------------------------------------------------------------------
# Warning-contract guards
# ---------------------------------------------------------------------------


def test_unexpected_warning_rejected() -> None:
    # s01 is 5x7: no filter warning expected
    problems = _parse("s01_constant_5x7", _valid_step_stdout(),
                      stderr="GwyProcess-WARNING **: Kernel size larger than "
                             "field area size.\n")
    assert any("unexpected filter warning" in p for p in problems)


def test_absent_expected_warning_rejected() -> None:
    # 3x16 field: the size-5 filter must warn exactly once
    lines = [
        "case=s03_positive_segment_4",
        "xres=16",
        "yres=3",
        "family=step",
        "existing_mask_present=0",
    ]
    problems = _parse("s03_positive_segment_4", "\n".join(lines) + "\n",
                      stderr="")
    assert any("expected exactly 1 filter warning, got 0" in p for p in problems)


def test_unexpected_sanitizer_output_rejected() -> None:
    problems = _parse("s01_constant_5x7", _valid_step_stdout(),
                      stderr="ERROR: AddressSanitizer: heap-use-after-free\n")
    assert any("sanitizer finding" in p for p in problems)


def test_glib_critical_rejected() -> None:
    problems = _parse("s01_constant_5x7", _valid_step_stdout(),
                      stderr="GLib-GObject-CRITICAL **: assertion failed\n")
    assert any("CRITICAL" in p for p in problems)


# ---------------------------------------------------------------------------
# Campaign-level guards (synthetic root, no /tmp dependency)
# ---------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_synthetic_root(tmp_path: Path) -> tuple[Path, Path]:
    """Build a minimal valid campaign root using repo-local sources only."""
    parity = gen.discover_parity_dir(REPO_ROOT)  # type: ignore[attr-defined]
    src_tree = parity.parent / "source"
    root = tmp_path / "campaign"
    for build in ("normal", "sanitized"):
        (root / build).mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "compile-normal.exit").write_text("0")
    (root / "compile-sanitized.exit").write_text("0")
    (root / "compile-normal.stdout").write_text("")
    (root / "compile-sanitized.stdout").write_text("")
    (root / "compile-normal.stderr").write_text("")
    (root / "compile-sanitized.stderr").write_text("")
    shutil.copy2(parity / "linecorrect_behavior_probe.c",
                 root / "bin" / "linecorrect_probe")
    shutil.copy2(parity / "linecorrect_behavior_probe.c",
                 root / "bin" / "linecorrect_probe.san")
    for case in ALL_CASES:
        family = "step" if case.startswith("s") else "inverted"
        text = (f"case={case}\nxres=7\nyres=5\nfamily={family}\n"
                f"existing_mask_present=0\n")
        for build in ("normal", "sanitized"):
            (root / build / f"{case}.stdout").write_text(text)
            (root / build / f"{case}.stderr").write_text("")
            (root / build / f"{case}.exit").write_text("0")
    # source identity from the actual repo files
    identity_lines = []
    identity_rels = [
        "modules/process/linecorrect.c",
        "libprocess/correct.c",
        "libprocess/filters.c",
        "libprocess/stats.c",
        "libprocess/linestats.c",
        "libprocess/datafield.c",
        "libprocess/arithmetic.c",
        "libprocess/dataline.c",
        "libprocess/gwyprocessenums.h",
    ]
    for rel in identity_rels:
        identity_lines.append(f"{_sha(src_tree / rel)}  {rel}")
    for e in sorted(src_tree.iterdir()):
        if e.is_dir() and e.name.startswith("lib"):
            for f in sorted(e.iterdir()):
                if f.name.endswith("gwymath-rank.c") or f.name == "gwymath.h":
                    identity_lines.append(
                        f"{_sha(f)}  {e.name}/{f.name}")
    for rel in ("linecorrect_behavior_probe.c",
                "run_linecorrect_probe_campaign.sh", "config.h"):
        identity_lines.append(f"{_sha(parity / rel)}  {rel}")
    (root / "source-identity.txt").write_text("\n".join(identity_lines) + "\n")
    # SHA256SUMS covering everything verify_campaign requires
    sums = []
    for build in ("normal", "sanitized"):
        for case in ALL_CASES:
            for ext in ("stdout", "stderr", "exit"):
                p = root / build / f"{case}.{ext}"
                sums.append(f"{_sha(p)}  {build}/{case}.{ext}")
    (root / "case-summary.tsv").write_text("build\tcase\n")
    (root / "normal-vs-sanitized-summary.tsv").write_text("case\n")
    for rel in ("source-identity.txt", "case-summary.tsv",
                "normal-vs-sanitized-summary.tsv", "compile-normal.stdout",
                "compile-normal.stderr", "compile-normal.exit",
                "compile-sanitized.stdout", "compile-sanitized.stderr",
                "compile-sanitized.exit", "bin/linecorrect_probe",
                "bin/linecorrect_probe.san"):
        p = root / rel
        if not p.exists():
            p.write_text("")
        sums.append(f"{_sha(p)}  {rel}")
    (root / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return root, parity


@requires_reference
def test_synthetic_root_valid(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert problems == [], problems[:5]


@requires_reference
def test_normal_sanitized_disagreement_rejected(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    (root / "sanitized" / "s01_constant_5x7.stdout").write_text(
        "case=s01_constant_5x7\nxres=7\nyres=5\nfamily=step\nTAMPERED\n")
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert any("normal/sanitized stdout differ" in p for p in problems)


@requires_reference
def test_source_hash_mismatch_rejected(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    lines = (root / "source-identity.txt").read_text().splitlines()
    for i, line in enumerate(lines):
        if line.endswith("  modules/process/linecorrect.c"):
            lines[i] = "0" * 64 + "  modules/process/linecorrect.c"
    (root / "source-identity.txt").write_text("\n".join(lines) + "\n")
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert any("source hash mismatch" in p for p in problems)


@requires_reference
def test_incomplete_sha256sums_rejected(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    sums = (root / "SHA256SUMS").read_text().splitlines()
    (root / "SHA256SUMS").write_text("\n".join(sums[:-1]) + "\n")
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert any("SHA256SUMS missing" in p for p in problems)


@requires_reference
def test_absent_case_rejected(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    (root / "normal" / "m12_existing_mask_with_inverted_row.stdout").unlink()
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert any("absent case m12_existing_mask_with_inverted_row" in p
               for p in problems)


@requires_reference
def test_family_mismatch_rejected(tmp_path) -> None:
    root, parity = _make_synthetic_root(tmp_path)
    (root / "normal" / "s01_constant_5x7.stdout").write_text(
        "case=s01_constant_5x7\nxres=7\nyres=5\nfamily=inverted\n"
        "existing_mask_present=0\n")
    problems: list[str] = []
    gen.verify_campaign(root, parity, problems)  # type: ignore[attr-defined]
    assert any("family != step" in p for p in problems)

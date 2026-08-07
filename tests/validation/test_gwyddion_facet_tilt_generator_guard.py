"""Focused tests for the facet-tilt fixture-generator cardinality guard.

The generator must reject any probe shifts vector that is not an exact,
unambiguous vector: parsed count equal to the source-derived expected
length, indices exactly ``range(expected_len)``, and no missing, extra,
negative, non-contiguous or duplicate indices.  This guards the same
class of failure that caused the original VERTICAL shifts defect, where
a probe emitting seven shifts was silently truncated to the assumed five.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_GENERATOR_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "gwyddion"
    / "facet_tilt"
    / "generate_fixtures.py"
)
_REAL_PROBE_ROOT = "/tmp/spmkit_gwyddion_facet_tilt_probe/normal"

_REAL_CASES = [
    "wide_curved_nomask",
    "wide_curved_includemask",
    "wide_curved_excludemask",
    "wide_curved_ignoremask",
    "constant_rows_5x4",
    "constant_rows_nonzero_5x4",
    "exactly_linear_rows",
    "nearly_linear_rows",
    "large_outlier",
    "repeated_outlier",
    "two_column_row",
    "vertical_direction",
    "fractional_mask",
    "fractional_mask_include",
    "two_column_vertical",
]


def _load_generator() -> Any:  # pragma: no cover
    spec = importlib.util.spec_from_file_location(
        "facet_tilt_generate_fixtures", str(_GENERATOR_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _write_stdout(
    tmp_path: Path,
    case_name: str,
    *,
    xres: int,
    yres: int,
    xreal: float,
    direction: str,
    shifts: list[int],
    extra_lines: list[str] | None = None,
) -> None:
    """Write a synthetic probe stdout with header KV lines and shifts lines."""
    lines = [
        "probe=gwyddion-2.71-facet-tilt-behavior",
        f"case={case_name}",
        f"xres={xres}",
        f"yres={yres}",
        f"xreal={xreal}",
        f"yreal={yres}",
        f"dx={xreal / xres}",
        f"{case_name}_direction={direction}",
        f"{case_name}_masking=IGNORE",
        f"{case_name}_do_extract=0",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    for index in shifts:
        lines.append(f"{case_name}_shifts_{index}=0.0")
    (tmp_path / f"{case_name}.stdout").write_text("\n".join(lines) + "\n")


@pytest.fixture()
def generator() -> Any:
    return _load_generator()


# ---------------------------------------------------------------------------
# Valid output continues to parse
# ---------------------------------------------------------------------------


def test_valid_horizontal_shifts_parse(tmp_path: Path, generator: Any) -> None:
    """HORIZONTAL 5x7 emits 5 shifts; parser returns (5,) unchanged."""
    _write_stdout(
        tmp_path, "valid_h", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 2, 3, 4],
    )
    arr = generator._parse_probe_line("valid_h", probe_root=str(tmp_path))
    assert arr is not None
    assert arr.shape == (5,)
    assert np.all(arr == 0.0)


def test_valid_vertical_shifts_parse(tmp_path: Path, generator: Any) -> None:
    """VERTICAL 5x7 emits 7 shifts (original xres); parser returns (7,)."""
    _write_stdout(
        tmp_path, "valid_v", xres=7, yres=5, xreal=5.6, direction="VERTICAL",
        shifts=[0, 1, 2, 3, 4, 5, 6],
    )
    arr = generator._parse_probe_line("valid_v", probe_root=str(tmp_path))
    assert arr is not None
    assert arr.shape == (7,)


# ---------------------------------------------------------------------------
# Exact-cardinality rejection
# ---------------------------------------------------------------------------


def test_missing_index_rejected(tmp_path: Path, generator: Any) -> None:
    """Fewer values than expected must fail loudly."""
    _write_stdout(
        tmp_path, "missing", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 2, 3],  # index 4 missing -> 4 vs expected 5
    )
    with pytest.raises(ValueError, match="missing.*expected indices.*count 5"):
        generator._parse_probe_line("missing", probe_root=str(tmp_path))


def test_extra_index_rejected(tmp_path: Path, generator: Any) -> None:
    """More values than expected must fail loudly (old guard missed this)."""
    _write_stdout(
        tmp_path, "extra", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 2, 3, 4, 5],  # 6 values vs expected 5
    )
    with pytest.raises(ValueError, match="extra.*expected indices.*count 5"):
        generator._parse_probe_line("extra", probe_root=str(tmp_path))


def test_historical_seven_emitted_five_expected_rejected(
    tmp_path: Path, generator: Any
) -> None:
    """The historical 7-emitted / 5-expected truncation must be rejected."""
    _write_stdout(
        tmp_path, "hist", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 2, 3, 4, 5, 6],  # 7 values vs expected 5
    )
    with pytest.raises(ValueError, match="hist.*count 7"):
        generator._parse_probe_line("hist", probe_root=str(tmp_path))


def test_non_contiguous_indices_rejected(tmp_path: Path, generator: Any) -> None:
    """A hole in the middle of the index set must fail loudly."""
    _write_stdout(
        tmp_path, "hole", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 3, 4],  # index 2 missing -> non-contiguous
    )
    with pytest.raises(ValueError, match="hole.*observed indices"):
        generator._parse_probe_line("hole", probe_root=str(tmp_path))


def test_duplicate_index_rejected(tmp_path: Path, generator: Any) -> None:
    """A repeated index must fail loudly instead of overwriting the value."""
    _write_stdout(
        tmp_path, "dup", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[0, 1, 2, 2, 3, 4],  # index 2 repeated
    )
    with pytest.raises(ValueError, match="dup.*duplicate index 2"):
        generator._parse_probe_line("dup", probe_root=str(tmp_path))


def test_negative_index_rejected(tmp_path: Path, generator: Any) -> None:
    """A negative index must fail loudly, not be skipped silently."""
    _write_stdout(
        tmp_path, "neg", xres=7, yres=5, xreal=5.6, direction="HORIZONTAL",
        shifts=[-1, 0, 1, 2, 3, 4],
    )
    with pytest.raises(ValueError, match="neg.*malformed element line"):
        generator._parse_probe_line("neg", probe_root=str(tmp_path))


def test_malformed_index_rejected(tmp_path: Path, generator: Any) -> None:
    """A non-integer index token must fail loudly for the shifts vector."""
    lines = [
        "case=malformed",
        "xres=7",
        "yres=5",
        "xreal=5.6",
        "yreal=5",
        "dx=0.8",
        "malformed_direction=HORIZONTAL",
        "malformed_masking=IGNORE",
        "malformed_do_extract=0",
        "malformed_shifts_x=0.0",
    ]
    for i in range(5):
        lines.append(f"malformed_shifts_{i}=0.0")
    (tmp_path / "malformed.stdout").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="malformed.*malformed element line"):
        generator._parse_probe_line("malformed", probe_root=str(tmp_path))


# ---------------------------------------------------------------------------
# Array parser: prefix-collision keys are skipped; duplicates still rejected
# ---------------------------------------------------------------------------


def test_array_parser_skips_prefix_collision_keys(tmp_path: Path, generator: Any) -> None:
    """Count/metric keys sharing the prefix must not confuse array parsing."""
    lines = [
        "case=collide",
        "xres=2",
        "yres=2",
        "xreal=2.0",
        "yreal=2",
        "dx=1.0",
        "collide_direction=HORIZONTAL",
        "collide_masking=IGNORE",
        "collide_do_extract=0",
        "collide_input_mutation_max_abs=1e-20",
        "collide_input_0=1.0",
        "collide_input_1=2.0",
        "collide_input_2=3.0",
        "collide_input_3=4.0",
    ]
    (tmp_path / "collide.stdout").write_text("\n".join(lines) + "\n")
    arr = generator._parse_probe_array("collide", "input", probe_root=str(tmp_path))
    assert arr is not None
    assert arr.shape == (2, 2)
    assert np.array_equal(arr, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_array_parser_duplicate_index_rejected(tmp_path: Path, generator: Any) -> None:
    """Duplicate pixel indices in a 2-D array must fail loudly."""
    lines = [
        "case=duparr",
        "xres=2",
        "yres=2",
        "xreal=2.0",
        "yreal=2",
        "dx=1.0",
        "duparr_direction=HORIZONTAL",
        "duparr_masking=IGNORE",
        "duparr_do_extract=0",
        "duparr_input_0=1.0",
        "duparr_input_1=2.0",
        "duparr_input_1=99.0",
        "duparr_input_2=3.0",
        "duparr_input_3=4.0",
    ]
    (tmp_path / "duparr.stdout").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="duparr.*duplicate index 1"):
        generator._parse_probe_array("duparr", "input", probe_root=str(tmp_path))


# ---------------------------------------------------------------------------
# Real campaign output still parses
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not Path(_REAL_PROBE_ROOT).is_dir(),
    reason="Real facet-tilt probe campaign output not present",
)
def test_real_campaign_shifts_parse(generator: Any) -> None:
    """The current valid 15-case probe output parses without changes."""
    for case_name in _REAL_CASES:
        kv = generator._parse_probe_kv(case_name)
        direction = kv.get(f"{case_name}_direction", "HORIZONTAL")
        expected = (
            int(kv["xres"]) if direction == "VERTICAL" else int(kv["yres"])
        )
        arr = generator._parse_probe_line(case_name)
        assert arr is not None, case_name
        assert arr.shape == (expected,), case_name
        assert np.all(arr == 0.0), case_name

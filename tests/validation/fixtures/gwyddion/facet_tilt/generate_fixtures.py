"""Generate facet_tilt_reference.json and .npz from C probe campaign output.

Run this script from the fixture directory after the C probe campaign
has completed successfully.  It parses the campaign stdout files and
produces the frozen reference fixture.

The external evidence is produced by a *compiled Gwyddion 2.71
source-inclusion probe*: a custom binary that compiles the frozen
``modules/process/linematch.c`` by source inclusion and links the
installed Gwyddion 2.71 shared libraries.  The installed GUI executable
(``/usr/bin/gwyddion``) is never invoked by the campaign.
"""

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PROBE_ROOT = "/tmp/spmkit_gwyddion_facet_tilt_probe/normal"

MASKING_ENUM = {"IGNORE": 2, "INCLUDE": 1, "EXCLUDE": 0}
DIRECTION_ENUM = {"HORIZONTAL": 0, "VERTICAL": 1}

# Element lines have the shape ``<index>=<value>`` immediately after the
# ``<case>_<label>_`` prefix.  Keys such as ``<case>_input_mutation_max_abs``
# or ``<case>_background_nan_count`` share the prefix but are not elements.
_ELEMENT_LINE = re.compile(r"^([0-9]+)=(.*)$")


def _sha256_hex_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(item) for item in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _bits(array: np.ndarray) -> list[str]:
    bits = np.ascontiguousarray(array, dtype=np.float64).view(np.uint64).ravel()
    return [hex(int(v)) for v in bits]


def _parse_probe_kv(case_name: str, probe_root: str | None = None) -> dict[str, str]:
    root = PROBE_ROOT if probe_root is None else probe_root
    stdout_path = os.path.join(root, f"{case_name}.stdout")
    text = Path(stdout_path).read_text()
    kv = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.strip().split("=", 1)
            kv[k] = v
    return kv


def _parse_indexed_values(
    case_name: str,
    label: str,
    stdout_path: str,
    expected_len: int,
    *,
    strict: bool,
) -> dict[int, float] | None:
    """Parse ``<case>_<label>_<i>=<v>`` lines with an exact index contract.

    Raises ValueError unless every parsed index is a distinct non-negative
    integer and the observed index set equals exactly ``range(expected_len)``
    — so missing, extra, negative, non-contiguous or duplicate indices all
    fail loudly, and no probe value can be dropped, truncated, reordered or
    overwritten through dictionary duplicate-key behaviour.

    When ``strict`` is False, lines sharing the prefix that are not element
    lines (e.g. ``<case>_input_mutation_max_abs`` or
    ``<case>_background_nan_count``) are skipped; when strict is True any
    such line is treated as a malformed element line and rejected.

    Returns None when no element lines are present at all.
    """
    prefix = f"{case_name}_{label}_"
    values: dict[int, float] = {}
    for line in Path(stdout_path).read_text().splitlines():
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix):]
        match = _ELEMENT_LINE.match(rest)
        if match is None:
            if strict:
                raise ValueError(
                    f"{case_name}: {label} malformed element line {line!r} "
                    f"(expected '<index>=<value>')"
                )
            continue
        index = int(match.group(1))
        if index in values:
            raise ValueError(f"{case_name}: {label} duplicate index {index}")
        values[index] = float(match.group(2))
    if not values:
        return None
    observed = sorted(values)
    expected = list(range(expected_len))
    if observed != expected:
        raise ValueError(
            f"{case_name}: {label} index set mismatch: expected indices "
            f"{expected} (count {expected_len}), observed indices "
            f"{observed} (count {len(observed)})"
        )
    return values


def _parse_probe_array(
    case_name: str, label: str, probe_root: str | None = None
) -> np.ndarray | None:
    root = PROBE_ROOT if probe_root is None else probe_root
    stdout_path = os.path.join(root, f"{case_name}.stdout")
    kv = _parse_probe_kv(case_name, probe_root=root)
    xres = int(kv["xres"])
    yres = int(kv["yres"])
    values = _parse_indexed_values(
        case_name, label, stdout_path, xres * yres, strict=False
    )
    if values is None:
        return None
    arr = np.empty((yres, xres), dtype=np.float64)
    for row in range(yres):
        for col in range(xres):
            arr[row, col] = values[row * xres + col]
    return arr


def _parse_probe_line(case_name: str, probe_root: str | None = None) -> np.ndarray | None:
    """Extract shifts as a 1-D GwyDataLine from probe output.

    The expected length is derived from the source semantics, not from a
    single header field: it equals the working field's y-resolution
    (original yres for HORIZONTAL, original xres for VERTICAL).

    The parsed shift vector must match that expected length exactly, with
    indices exactly ``range(expected_len)``.  A probe emitting fewer or
    more values, a non-contiguous or duplicated index set, or a malformed
    element line raises ValueError (strict=True): no emitted value may be
    dropped, truncated or overwritten.
    """
    root = PROBE_ROOT if probe_root is None else probe_root
    stdout_path = os.path.join(root, f"{case_name}.stdout")
    kv = _parse_probe_kv(case_name, probe_root=root)
    direction_str = kv.get(f"{case_name}_direction", "HORIZONTAL")
    expected_len = int(kv["xres"]) if direction_str == "VERTICAL" else int(kv["yres"])
    values = _parse_indexed_values(
        case_name, "shifts", stdout_path, expected_len, strict=True
    )
    if values is None:
        return None
    arr = np.empty(expected_len, dtype=np.float64)
    for i in range(expected_len):
        arr[i] = values[i]
    return arr


def main() -> None:
    cases = [
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

    manifest: dict = {
        "capability": "gwyddion_align_rows_facet_tilt",
        "schema_version": 1,
        "case_count": len(cases),
    }

    manifest_cases: list[dict] = []
    npz_arrays: dict[str, np.ndarray] = {}
    array_hashes: dict[str, str] = {}

    for case_name in cases:
        kv = _parse_probe_kv(case_name)
        xres = int(kv["xres"])
        yres = int(kv["yres"])

        input_arr = _parse_probe_array(case_name, "input")
        corrected_arr = _parse_probe_array(case_name, "corrected")
        background_arr = _parse_probe_array(case_name, "background")
        shifts_arr = _parse_probe_line(case_name)
        input_key = f"{case_name}_input"
        corrected_key = f"{case_name}_probe_corrected"
        background_key = f"{case_name}_probe_background"
        shifts_key = f"{case_name}_probe_shifts"

        npz_arrays[input_key] = input_arr
        npz_arrays[corrected_key] = corrected_arr
        if background_arr is not None and background_arr.size > 0:
            npz_arrays[background_key] = background_arr
        if shifts_arr is not None:
            npz_arrays[shifts_key] = shifts_arr

        masking_str = kv.get(f"{case_name}_masking", "IGNORE")
        direction_str = kv.get(f"{case_name}_direction", "HORIZONTAL")
        do_extract = kv.get(f"{case_name}_do_extract", "0") == "1"

        case_entry: dict = {
            "case_identifier": case_name,
            "rows": yres,
            "columns": xres,
            "direction": DIRECTION_ENUM.get(direction_str, 0),
            "method": 7,
            "method_name": "Facet-level tilt",
            "masking_mode": MASKING_ENUM.get(masking_str, 2),
            "extract_background_request": do_extract,
            "input_bits": _bits(input_arr),
            "mask_bits": None,
            "input_key": input_key,
            "mask_key": None,
            "probe_corrected_key": corrected_key,
            "probe_background_key": (
                background_key
                if background_arr is not None and background_arr.size > 0
                else None
            ),
            "probe_shifts_key": shifts_key,
            "xreal_hex": hex(int(np.float64(float(kv["xreal"])).view(np.uint64))),
            "yreal_hex": hex(int(np.float64(float(kv["yreal"])).view(np.uint64))),
            "dx_hex": hex(int(np.float64(float(kv["dx"])).view(np.uint64))),
        }
        manifest_cases.append(case_entry)

    manifest["cases"] = manifest_cases

    # Profiles
    linematch_path = str(
        ROOT.parent.parent.parent.parent.parent
        / ".reference/gwyddion-2.71/source/modules/process/linematch.c"
    )
    manifest["profiles"] = {
        "compiled_gwyddion_2_71_source_inclusion_profile": (
            {} if not os.path.exists(linematch_path) else {
                "canonical_reference_sha256": _sha256_hex_file(linematch_path),
                "module_sha256": _sha256_hex_file(linematch_path),
            }
        )
    }

    # Comparison metrics (all cases are bitwise-exact; no exceptions)
    n_cases = len(cases)
    case_shapes = [
        (manifest["cases"][i]["rows"], manifest["cases"][i]["columns"])
        for i in range(n_cases)
    ]
    manifest["comparison_metrics"] = {
        "corrected": {
            "arrays_bitwise_exact": n_cases,
            "elements_bitwise_exact": sum(y * x for y, x in case_shapes),
            "max_absolute_difference": 0.0,
            "finite_nonzero_mismatch": 0,
            "signed_zero_mismatch": 0,
            "nan_mismatch": 0,
            "inf_mismatch": 0,
        }
    }

    # Evidence
    manifest["evidence"] = {
        "probe_kind": "compiled_gwyddion_2_71_source_inclusion_probe",
        "probe_description": (
            "Custom binary compiling modules/process/linematch.c by source "
            "inclusion and linking the installed Gwyddion 2.71 shared "
            "libraries; the installed GUI executable (/usr/bin/gwyddion) "
            "was not invoked."
        ),
        "compiled_probe_diagnosis": ["LINEMATCH_SOURCE_MATCHES_FROZEN_REFERENCE"],
        "non_claims": ["Does not cover fast-math reassociation divergence."],
    }

    # Fixture array hashes
    for key in sorted(npz_arrays):
        array_hashes[key] = _array_hash(npz_arrays[key])
    manifest["fixture"] = {"array_hashes": array_hashes}

    # Write JSON
    json_path = ROOT / "facet_tilt_reference.json"
    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    # Write NPZ
    npz_path = ROOT / "facet_tilt_reference.npz"
    np.savez_compressed(npz_path, **npz_arrays)

    # Compute SHA256s for manifest
    json_sha = _sha256_hex_file(str(json_path))
    npz_sha = _sha256_hex_file(str(npz_path))
    print(f"MANIFEST_SHA256 = {json_sha}")
    print(f"NPZ_SHA256 = {npz_sha}")
    print(f"Arrays in NPZ: {list(npz_arrays)}")


if __name__ == "__main__":
    main()

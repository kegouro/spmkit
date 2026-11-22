"""Compare default and matched-axis Hertz fits to nanite on the 110 public PAAm curves."""

import argparse
import csv
import math
import sys
from pathlib import Path

import nanite

from spmkit.core.analysis.forcecurve import display_axis, fit_force_curve
from spmkit.core.export.manifest import file_sha256
from spmkit.core.io.jpk import load_jpk_force


def modulus(x, force):
    return fit_force_curve(x, force, model="sphere", tip_radius=5e-6, poisson=0.3).young_modulus


def compare(path):
    seg = load_jpk_force(path).extend
    default = modulus(display_axis(seg.separation, seg.raw_height), seg.force)
    independent = nanite.IndentationGroup(path)[0]
    approach = independent["segment"] == 0
    # Change only x. Keep the native reader's force vector and the SPM-Kit fitter.
    measured_height = independent["height (measured)"][approach]
    tip_position = (
        measured_height + independent["force"][approach] / independent.metadata["spring constant"]
    )
    sensor_axis = modulus(tip_position, seg.force)
    independent.apply_preprocessing(
        ["compute_tip_position", "correct_force_offset", "correct_tip_offset"]
    )
    params = independent.get_initial_fit_parameters(model_key="hertz_para")
    params["R"].set(value=5e-6, vary=False)
    params["nu"].set(value=0.3, vary=False)
    independent.fit_model(model_key="hertz_para", params_initial=params, segment=0, weight_cp=0)
    if not independent.fit_properties["success"]:
        raise ValueError("nanite fit failed")
    matched = modulus(independent["tip position"][approach], independent["force"][approach])
    values = default, sensor_axis, matched, independent.fit_properties["params_fitted"]["E"].value
    if not all(value is not None and math.isfinite(value) and value > 0 for value in values):
        raise ValueError(f"Invalid modulus: {path.name}")
    return values


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("checksums", type=Path, help="Publisher's sha256.txt")
    parser.add_argument("batch", type=Path, help="CSV exported by fbatch with a 5 µm tip")
    args = parser.parse_args()
    with args.batch.open(newline="") as stream:
        batch_rows = list(csv.DictReader(line for line in stream if not line.startswith("#")))
    batch = {row["source"]: row for row in batch_rows}
    if len(batch_rows) != 110 or len(batch) != 110:
        raise ValueError("Expected 110 distinct files in the batch")
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(
        [
            "source",
            "sha256",
            "fbatch_pa",
            "spmkit_default_pa",
            "spmkit_sensor_axis_pa",
            "spmkit_matched_pa",
            "nanite_pa",
        ]
    )
    seen = set()
    for line in args.checksums.read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        if not name.endswith(".jpk-force"):
            continue
        path = args.root / name
        if name in seen or path.parent != args.root:
            raise ValueError(f"Unexpected checksum entry: {name}")
        if file_sha256(path) != expected:
            raise ValueError(f"Digest mismatch: {name}")
        row = batch[name]
        if row["source_sha256"] != expected or row["error"] or row["n_young_modulus"] != "1":
            raise ValueError(f"Invalid batch measurement: {name}")
        batch_pa = float(row["young_modulus_median [Pa]"])
        if not math.isfinite(batch_pa):
            raise ValueError(f"Non-finite batch result: {name}")
        writer.writerow([name, expected, batch_pa, *compare(path)])
        seen.add(name)
    if len(seen) != 110:
        raise ValueError(f"Incomplete v3 dataset: {len(seen)} curves")

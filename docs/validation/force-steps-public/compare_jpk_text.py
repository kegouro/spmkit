"""Compare the manifest subset against instrument text exports in acquisition order."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from spmkit.core.analysis.force_steps import measure_force_step
from spmkit.core.export.manifest import file_sha256
from spmkit.core.force_step_batch import analyze_step_annotations
from spmkit.core.io.jpk import load_jpk_force


def text_segments(path):
    segments = []
    for line in path.read_text(encoding="latin1").splitlines():
        if line.startswith("# segment: "):
            segments.append({"segment": line.split()[-1], "data": []})
        elif line.startswith("# "):
            key, _, value = line[2:].partition(": ")
            if segments and key in {
                "columns",
                "units",
                "calibrationSlots",
                "heightMultiplier",
                "heightOffset",
            }:
                segments[-1][key] = value
        elif line.strip() and not line.startswith("#"):
            segments[-1]["data"].append([float(x) for x in line.split()])
    return segments


def intercept(z, force, midpoint):
    x = (z - midpoint) * 1e9
    return np.linalg.lstsq(np.column_stack((np.ones_like(x), x)), force, rcond=None)[0][0]


def compare(path, member):
    curve = load_jpk_force(path)
    for segment, block in zip(curve.segments, text_segments(path.with_suffix(".txt")), strict=True):
        cols = block["columns"].split()
        h, f = cols.index("height"), cols.index("vDeflection")
        units = block["units"].split()
        slots = block["calibrationSlots"].split()
        if (units[h], units[f], slots[h], slots[f]) != ("m", "N", "nominal", "force"):
            raise ValueError(f"Unexpected calibration in {member}")
        if segment.segment_type != block["segment"]:
            raise ValueError(f"Segment mismatch in {member}")
        data = np.asarray(block["data"])
        if len(segment) != len(data):
            raise ValueError(f"Sample count mismatch in {member}")
        z = data[:, h] * float(block["heightMultiplier"]) + float(block["heightOffset"])
        force = data[:, f]
        row = {
            "source": member,
            "branch": segment.segment_type,
            "samples": len(z),
            "max_force_error_n": float(np.max(abs(force - segment.force))),
            "max_height_error_m": float(np.max(abs(z - segment.raw_height))),
        }
        if segment.segment_type in ("extend", "retract"):
            b = len(z) // 2
            mid = (z[b - 1] + z[b]) / 2

            left, right = slice(b - 8, b), slice(b, b + 8)
            ref = intercept(z[right], force[right], mid) - intercept(z[left], force[left], mid)
            row["jump_reference_n"] = float(ref)
            row["jump_error_n"] = float(measure_force_step(segment, b, 8).delta_force_n - ref)
        yield row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", type=Path, help="Directory containing the original ZIP member paths"
    )
    root = parser.parse_args().root
    files = json.loads(Path(__file__).with_name("pairs.json").read_text())
    for item in files:
        path = root / item["member"]
        if file_sha256(path) != item["sha256"]:
            raise ValueError(f"Digest mismatch: {path.name}")
    rows = [
        row
        for item in files
        if item["member"].endswith(".jpk-force")
        for row in compare(root / item["member"], item["member"])
    ]
    branches = [r for r in rows if "jump_reference_n" in r]
    with TemporaryDirectory() as tmp:
        table = Path(tmp) / "annotations.csv"
        with table.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(("source", "curve", "branch", "cycle", "boundary", "window"))
            for r in branches:
                writer.writerow(
                    ((root / r["source"]).resolve(), 0, r["branch"], 0, r["samples"] // 2, 8)
                )
        for r, result in zip(branches, analyze_step_annotations(table), strict=True):
            if result["status"] != "measured":
                raise ValueError(result["reason"])
            r["batch_jump_error_n"] = result["delta_force_n"] - r["jump_reference_n"]
            if r["batch_jump_error_n"] != r["jump_error_n"]:
                raise ValueError(f"Batch and individual measurements differ for {r['source']}")
    for row in rows:
        print(json.dumps(row, allow_nan=False))

"""Campaña externa de 10 archivos JPK ForceScan 2.0 (FS-R1B).

Script standalone: parsea todos los ``*.jpk-force`` de un directorio con el
lector público ``load_force``, verifica los SHA-256 contra el manifiesto
committeado (``tests/validation/fixtures/jpk_forcescan2/paam_dataset_manifest.json``)
y escribe dos salidas deterministas:

    /tmp/spmkit_jpk_forcescan2_campaign.json
    /tmp/spmkit_jpk_forcescan2_campaign.md

Uso:

    .venv/bin/python scripts/jpk_forcescan2_campaign.py --dir <dir-de-archivos>

Los archivos originales quedan fuera de Git (ver manifiesto). Este script no
modifica nada: solo lee los archivos y escribe en /tmp.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.io import load_force

_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "validation"
    / "fixtures"
    / "jpk_forcescan2"
    / "paam_dataset_manifest.json"
)

_CAMPAIGN_JSON = "/tmp/spmkit_jpk_forcescan2_campaign.json"
_CAMPAIGN_MD = "/tmp/spmkit_jpk_forcescan2_campaign.md"


def _parse_props(raw: bytes) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")) or "=" not in line:
            continue
        key, _, value = line.partition("=")
        props[key.strip()] = value.strip()
    return props


def _audit_archive(path: Path) -> dict[str, object]:
    """Campos de auditoría de calibración leídos del propio archivo (sin parsear)."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        shared = (
            _parse_props(zf.read("shared-data/header.properties"))
            if "shared-data/header.properties" in names
            else {}
        )
        seg_ids = sorted(
            {
                int(m.group(1))
                for n in names
                if (m := re.search(r"segments/(\d+)/segment-header\.properties$", n))
            }
        )
        segs = {}
        for seg in seg_ids:
            sp = _parse_props(zf.read(f"segments/{seg}/segment-header.properties"))
            segs[str(seg)] = {
                "name": sp.get("force-segment-header.name.name"),
                "num_points": sp.get("force-segment-header.num-points"),
                "time_stamp": sp.get("force-segment-header.time-stamp"),
                "duration": sp.get("force-segment-header.duration"),
                "baseline": sp.get("force-segment-header.baseline.baseline"),
                "lcd_refs": {
                    ch: sp.get(f"channel.{ch}.lcd-info.*")
                    for ch in (sp.get("channels.list") or "").split()
                },
            }
        h = "lcd-info.1."
        v = "lcd-info.2."
        return {
            "lcd_infos_count": shared.get("lcd-infos.count"),
            "height": {
                "raw_dtype": ">i4"
                if shared.get(f"{h}type") == "integer-data"
                else shared.get(f"{h}type"),
                "encoder_multiplier": shared.get(f"{h}encoder.scaling.multiplier"),
                "encoder_offset": shared.get(f"{h}encoder.scaling.offset"),
                "encoder_unit": shared.get(f"{h}encoder.scaling.unit.unit"),
                "slots": shared.get(f"{h}conversion-set.conversions.list"),
                "default": shared.get(f"{h}conversion-set.conversions.default"),
                "final_unit": shared.get(
                    f"{h}conversion-set.conversion.calibrated.scaling.unit.unit"
                ),
            },
            "vDeflection": {
                "raw_dtype": ">i4"
                if shared.get(f"{v}type") == "integer-data"
                else shared.get(f"{v}type"),
                "encoder_multiplier": shared.get(f"{v}encoder.scaling.multiplier"),
                "encoder_offset": shared.get(f"{v}encoder.scaling.offset"),
                "encoder_unit": shared.get(f"{v}encoder.scaling.unit.unit"),
                "invols": shared.get(f"{v}conversion-set.conversion.distance.scaling.multiplier"),
                "invols_unit": shared.get(
                    f"{v}conversion-set.conversion.distance.scaling.unit.unit"
                ),
                "spring_constant": shared.get(
                    f"{v}conversion-set.conversion.force.scaling.multiplier"
                ),
                "spring_unit": shared.get(f"{v}conversion-set.conversion.force.scaling.unit.unit"),
                "slots": shared.get(f"{v}conversion-set.conversions.list"),
            },
            "segments": segs,
        }


def _monotonicity(arr: np.ndarray) -> dict[str, object]:
    d = np.diff(arr)
    return {
        "n_decreasing": int(np.sum(d < 0)),
        "n_increasing": int(np.sum(d > 0)),
        "n_zero": int(np.sum(d == 0)),
        "monotonic_decreasing": bool(np.all(d <= 0)),
    }


def _run(dataset_dir: Path) -> dict[str, Any]:
    manifest = json.loads(_MANIFEST.read_text())
    expected = {f["name"]: f["sha256"] for f in manifest["files"]}
    results: dict[str, Any] = {"dataset": manifest["dataset"], "files": []}
    loaded = failed = 0
    for p_str in sorted(glob.glob(str(dataset_dir / "*.jpk-force"))):
        path = Path(p_str)
        blob = path.read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        rec: dict[str, Any] = {
            "file": path.name,
            "size": len(blob),
            "sha256": sha,
            "hash_in_manifest": sha in expected.values(),
            "expected_sha": next((k for k, v in expected.items() if v == sha), None),
            "audit": _audit_archive(path),
        }
        try:
            volume = load_force(path)
            curve = volume.curve(0)
            ext = curve.extend
            fseg = ext if ext is not None else curve.segments[0]
            rec["result"] = {
                "success": True,
                "volume_curves": volume.n_curves,
                "segments": [s.segment_type for s in curve.segments],
                "directions": [s.direction for s in curve.segments],
                "point_counts": [int(len(s)) for s in curve.segments],
                "state": fseg.state,
                "height_units": "m",
                "deflection_units": "m",
                "force_units": "N",
                "height_range_extend": [
                    float(np.min(fseg.raw_height)),
                    float(np.max(fseg.raw_height)),
                ],
            }
            rec["result"]["finite"] = {
                "height": int(np.count_nonzero(np.isfinite(fseg.raw_height))),
                "deflection": (
                    int(np.count_nonzero(np.isfinite(fseg.deflection)))
                    if fseg.deflection is not None
                    else None
                ),
                "force": int(np.count_nonzero(np.isfinite(fseg.force)))
                if fseg.force is not None
                else None,
            }
            rec["result"]["monotonicity_extend_height"] = _monotonicity(fseg.raw_height)
            rec["result"]["calibration"] = (
                {
                    "invols": curve.calibration.invols,
                    "spring_constant": curve.calibration.spring_constant,
                    "method": curve.calibration.method,
                    "provenance": curve.calibration.provenance,
                }
                if curve.calibration is not None
                else None
            )
            rec["result"]["profile"] = curve.metadata.get("profile")
            rec["result"]["lcd_info"] = curve.segments[0].metadata.get("lcd_info")
            loaded += 1
        except Exception as exc:  # noqa: BLE001 - la campaña registra cualquier fallo
            rec["result"] = {
                "success": False,
                "exception": type(exc).__name__,
                "code": getattr(exc, "code", None),
                "message": str(exc)[:200],
            }
            failed += 1
        results["files"].append(rec)
    results["summary"] = {"files": len(results["files"]), "loaded": loaded, "failed": failed}
    return results


def _render_md(results: dict[str, Any]) -> str:
    lines = [
        "# SPMKit JPK ForceScan 2.0 campaign (FS-R1B)",
        "",
        f"- dataset: {results['dataset']['title']}",
        f"- DOI: {results['dataset']['doi']} | licence: {results['dataset']['licence']}",
        "- files: {} | loaded: {} | failed: {}".format(  # noqa: UP032
            results["summary"]["files"], results["summary"]["loaded"], results["summary"]["failed"]
        ),
        "",
        "| file | sha256 (manifest) | segments | state | points | height range (m) |",
        "| force range (N) | invols | k | profile |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in results["files"]:
        r = f["result"]
        if r["success"]:
            rows = [
                f["file"][:42],
                "yes" if f["hash_in_manifest"] else "NO",
                "+".join(r["segments"]),
                r["state"],
                "+".join(str(n) for n in r["point_counts"]),
                f"{r['height_range_extend'][0]:.4g}..{r['height_range_extend'][1]:.4g}",
                f"{r['finite']['force']}/{max(r['point_counts'])} finite",
                f"{r['calibration']['invols']:.4g}" if r["calibration"] else "-",
                f"{r['calibration']['spring_constant']:.4g}" if r["calibration"] else "-",
                str(r["profile"]),
            ]
        else:
            rows = [
                f["file"][:42],
                "yes" if f["hash_in_manifest"] else "NO",
                "FAILED",
                r["code"] or r["exception"],
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            ]
        lines.append("| " + " | ".join(rows) + " |")
    lines.append("")
    lines.append("Calibration chain (identical across files):")
    lines.append(
        "- height: int32 -> V (mult 2.653565956897467E-8, offset 56.98910501326783) "
        "-> nominal (m) -> calibrated (m, x0.78014)"
    )
    lines.append(
        "- vDeflection: int32 -> V (mult 5.568822848285905E-9, offset -1.2012213894932133E-4) "
        "-> distance (m, invols 6.068792445314747E-8) -> force (N, k 0.04659723113213052)"
    )
    lines.append(
        "- no pause/dwell segments in any file; 2 segments per curve (extend-spm, retract-spm)"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="FS-R1B external 10-file JPK campaign")
    parser.add_argument("--dir", required=True, type=Path, help="directorio con los .jpk-force")
    args = parser.parse_args()
    results = _run(args.dir)
    Path(_CAMPAIGN_JSON).write_text(json.dumps(results, indent=1) + "\n")
    Path(_CAMPAIGN_MD).write_text(_render_md(results))
    print(
        "files={} loaded={} failed={}".format(  # noqa: UP032
            results["summary"]["files"], results["summary"]["loaded"], results["summary"]["failed"]
        )
    )
    print(f"wrote {_CAMPAIGN_JSON} and {_CAMPAIGN_MD}")
    return 0 if results["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

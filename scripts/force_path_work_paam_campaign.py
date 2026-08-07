"""Campaña real FS-R1C: path work sobre los 10 archivos PAAm externos.

Script standalone.  Para cada ``*.jpk-force`` del directorio:

    load_force -> calibrate -> tip-sample separation -> baseline/contact
    -> integrate_force_path_work (orden de adquisición, sin reparar nada)

Verifica los SHA-256 contra el manifiesto committeado y escribe salidas
deterministas en /tmp:

    /tmp/spmkit_force_path_work_paam_campaign.json
    /tmp/spmkit_force_path_work_paam_campaign.md

Uso:

    .venv/bin/python scripts/force_path_work_paam_campaign.py --dir <dir>

El trabajo medido NO se interpreta como energía de material validada.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from spmkit.core.analysis import (
    calibrate_force_curve,
    compute_tip_sample_separation,
    contact_point_ensemble,
    correct_force_baseline,
    fit_force_baseline,
    integrate_force_path_work,
)
from spmkit.core.io import load_force

_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "validation"
    / "fixtures"
    / "jpk_forcescan2"
    / "paam_dataset_manifest.json"
)
_CAMPAIGN_JSON = "/tmp/spmkit_force_path_work_paam_campaign.json"
_CAMPAIGN_MD = "/tmp/spmkit_force_path_work_paam_campaign.md"


def _run(dataset_dir: Path) -> dict:
    manifest = json.loads(_MANIFEST.read_text())
    expected = {f["name"]: f["sha256"] for f in manifest["files"]}
    results: dict = {"dataset": manifest["dataset"], "files": []}
    for p_str in sorted(glob.glob(str(dataset_dir / "*.jpk-force"))):
        path = Path(p_str)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        rec: dict = {
            "file": path.name,
            "sha256": sha,
            "hash_in_manifest": sha in expected.values(),
        }
        try:
            curve = load_force(path).curve(0)
            calibrated = calibrate_force_curve(curve).curve
            sep_curve = compute_tip_sample_separation(calibrated)
            baseline = fit_force_baseline(sep_curve, model="linear")
            correct_force_baseline(sep_curve, baseline, scope="all")
            contact = contact_point_ensemble(
                sep_curve,
                methods=("threshold", "ratio_of_variances", "piecewise"),
                bootstrap_samples=0,
            )
            ext = sep_curve.extend
            if ext is None or ext.separation is None or ext.force is None:
                raise ValueError("extend segment without separation/force")
            z = np.asarray(ext.separation, dtype=np.float64)
            f = np.asarray(ext.force, dtype=np.float64)
            work = integrate_force_path_work(
                z,
                f,
                provenance={"file": path.name, "segment": "extend", "axis": "separation"},
            )
            d = work.diagnostics
            rec["result"] = {
                "success": True,
                "curves": 1,
                "segment": "extend",
                "samples": d.n_samples,
                "net_displacement": d.net_displacement,
                "total_variation": d.total_variation,
                "forward_distance": d.forward_distance,
                "backward_distance": d.backward_distance,
                "backtracking_fraction": d.backtracking_fraction,
                "exact_positive_steps": d.exact_positive_steps,
                "exact_negative_steps": d.exact_negative_steps,
                "exact_zero_steps": d.exact_zero_steps,
                "maximum_reverse_step": d.maximum_reverse_step,
                "maximum_reverse_excursion": d.maximum_reverse_excursion,
                "global_direction": d.global_direction,
                "strictly_monotonic": d.strictly_monotonic,
                "globally_directed": d.globally_directed,
                "path_work_j": work.work_total,
                "work_forward_j": work.work_forward,
                "work_backward_j": work.work_backward,
                "absolute_accumulated_work_j": work.absolute_accumulated_work,
                "units": work.units,
                "contact_agreement": contact.method_agreement,
                "contact_coordinate": contact.selected.coordinate,
                "baseline_slope": baseline.slope,
                "warnings": list(work.warnings),
            }
        except Exception as exc:  # noqa: BLE001 - la campaña registra cualquier fallo
            rec["result"] = {
                "success": False,
                "exception": type(exc).__name__,
                "code": getattr(exc, "code", None),
                "message": str(exc)[:200],
            }
        results["files"].append(rec)
    results["summary"] = {
        "files": len(results["files"]),
        "loaded": sum(1 for f in results["files"] if f["result"]["success"]),
        "failed": sum(1 for f in results["files"] if not f["result"]["success"]),
    }
    return results


def _render_md(results: dict) -> str:
    lines = [
        "# FS-R1C PAAm acquisition-path work campaign",
        "",
        f"- dataset: {results['dataset']['title']}",
        f"- DOI: {results['dataset']['doi']} | licence: {results['dataset']['licence']}",
        f"- files: {results['summary']['files']} | loaded: {results['summary']['loaded']} | "
        f"failed: {results['summary']['failed']}",
        "",
        "| file | sha (manifest) | samples | net disp (m) | total var (m) | backtrack frac "
        "| neg/pos/zero steps | max rev step (m) | max rev exc (m) | direction | path work (J) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in results["files"]:
        r = f["result"]
        if r["success"]:
            rows = [
                f["file"][:36],
                "yes" if f["hash_in_manifest"] else "NO",
                str(r["samples"]),
                f"{r['net_displacement']:.4e}",
                f"{r['total_variation']:.4e}",
                f"{r['backtracking_fraction']:.3f}",
                f"{r['exact_negative_steps']}/{r['exact_positive_steps']}/{r['exact_zero_steps']}",
                f"{r['maximum_reverse_step']:.2e}",
                f"{r['maximum_reverse_excursion']:.2e}",
                r["global_direction"],
                f"{r['path_work_j']:.5e}",
            ]
        else:
            rows = [f["file"][:36], "yes" if f["hash_in_manifest"] else "NO", "FAILED",
                    r["code"] or r["exception"], "-", "-", "-", "-", "-", "-", "-"]
        lines.append("| " + " | ".join(rows) + " |")
    lines.append("")
    lines.append(
        "Definition: W = sum_i 0.5*(F_i + F_{i+1})*(z_{i+1} - z_i) en orden de adquisición;"
    )
    lines.append("dz firmados, sin ordenar/suavizar/eliminar; tolerancia solo de clasificación.")
    lines.append(
        "El trabajo medido NO es energía de material validada ni energía de adhesión por área."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="FS-R1C external PAAm path-work campaign")
    parser.add_argument("--dir", required=True, type=Path)
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

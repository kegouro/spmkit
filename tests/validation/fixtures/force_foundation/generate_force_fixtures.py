"""Assemble the persistent force-foundation fixture bundle.

Sources:
  * PHANTOM_GROUND_TRUTH: deterministic phantom family (manifest + arrays);
  * NANITE_EXTERNAL_REFERENCE: pinned nanite 4.2.3 black-box outputs for the
    overlapping retained cases (stored compactly; never canonical for native
    ROV/ensemble/event/work/QC contracts);
  * NATIVE_SPMKIT_CONTRACT: the frozen contract summary;
  * RELATION_ONLY: declared metamorphic relations.

Deterministic and byte-stable across regeneration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent
CAMPAIGN_OUTPUT = (
    Path(__file__).resolve().parents[4]
    / ".reference"
    / "force-spectroscopy"
    / "nanite-reference"
    / "campaign_output.json"
)


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    from generate_force_phantoms import generate_phantoms, serialize

    phantoms = generate_phantoms()
    serialize(phantoms, FIXTURE_DIR)

    # nanite external outputs
    external = json.loads(CAMPAIGN_OUTPUT.read_text())
    manifest = {
        "schema_version": 1,
        "family": "force_foundation",
        "phantom_manifest": FIXTURE_DIR.name + "/force_phantoms_reference.json",
        "external_reference": {
            "software": "nanite",
            "version": "4.2.3",
            "license": "GPL-3 (subprocess boundary only)",
            "python": "3.12.13",
            "platform": "Linux-x86_64-glibc",
            "pipeline": [
                "compute_tip_position",
                "correct_split_approach_retract",
                "correct_tip_offset",
                "correct_force_offset",
                "correct_force_slope",
            ],
            "contact_methods": [
                "deviation_from_baseline",
                "fit_constant_line",
                "fit_line_polynomial",
                "fit_constant_polynomial",
            ],
            "cases": {
                o["case_id"]: {
                    "tip_position": o["tip_position"],
                    "force": o["force"],
                    "height": o["height"],
                    "segment": o["segment"],
                    "contact": {
                        "deviation_from_baseline": o.get("contact_deviation_from_baseline"),
                        "fit_constant_line": o.get("contact_fit_constant_line"),
                        "fit_line_polynomial": o.get("contact_fit_line_polynomial"),
                        "fit_constant_polynomial": o.get("contact_fit_constant_polynomial"),
                    },
                }
                for o in external
            },
            "campaign_input_sha256": _sha256(CAMPAIGN_OUTPUT),
        },
        "native_contract": {
            "calibration": "raw_v -> deflection_m (x InVOLS m/V) -> force_n (x k N/m)",
            "separation": "height - deflection",
            "baseline": "pre_contact = first 10% of approach; linear offset + slope",
            "contact": "threshold (k*sigma, persistence 3) / ROV (Gavara) / piecewise (1/2, value-continuous)",
            "events": "snap-in on approach before contact; pull-off on retract",
            "work": "trapezoid over common tip-position overlap; monotone interpolation",
            "qc": "typed reasons; summary score beside component diagnostics",
        },
        "relations": {
            "force_scaling": "force scales linearly with spring constant",
            "deflection_scaling": "deflection scales with InVOLS",
            "baseline_offset_invariance": "offset correction leaves contact branch shape invariant",
            "work_scaling": "work scales linearly with force amplitude",
            "event_window_restriction": "restricting event windows bounds the search",
        },
        "non_claims": [
            "no certified cantilever calibration",
            "no universal JPK/ANA numerical parity",
            "no physical validation",
            "no universal contact point",
            "no automatic choice of the correct contact method",
            "no uncertainty guarantee from method spread alone",
            "no model validity inference",
            "no cell/material property truth claim",
            "no experimental reproducibility claim",
            "no complete force-map parity",
            "no SMFS or viscoelastic parity from this batch",
        ],
    }
    (FIXTURE_DIR / "force_foundation_reference.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    # external arrays in a compact npz
    arrays = {}
    for o in external:
        for key in ("tip_position", "force", "height", "segment"):
            arrays[f"nanite_{o['case_id']}_{key}"] = np.asarray(o[key], dtype=np.float64)
    np.savez_compressed(
        FIXTURE_DIR / "force_foundation_external.npz", **{k: arrays[k] for k in sorted(arrays)}
    )
    print("force foundation fixtures written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

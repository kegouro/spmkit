#!/usr/bin/env python3
"""Generate docs/parity/CAPABILITY_LEDGER.md from the packaged capability
ledger JSON (src/spmkit/core/capabilities.json).

The Markdown is generated output, not a hand-maintained source of truth.
Regeneration is byte-identical: no timestamps, absolute paths, branch or
commit metadata are emitted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_JSON = REPO_ROOT / "src" / "spmkit" / "core" / "capabilities.json"
OUTPUT_MD = REPO_ROOT / "docs" / "parity" / "CAPABILITY_LEDGER.md"

_FAMILY_TITLES = {
    "IMG.LEVEL": "Leveling",
    "IMG.BACKGROUND": "Background",
    "IMG.SCANLINE": "Scan-line corrections",
    "IMG.FILTER": "Neighborhood filters",
    "IMG.MORPH": "Morphology",
    "IMG.STATS": "Statistics",
    "IMG.INTERPOLATION": "Interpolation",
}


def render(records: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# SPMKit Capability Ledger")
    lines.append("")
    lines.append("Stable scientific capabilities registered by the Operation "
                 "Registry v1.")
    lines.append("")
    lines.append(f"- schema_version: {records[0]['schema_version'] if False else 1}")
    lines.append(f"- operations: {len(records)}")
    lines.append("")
    lines.append("Source of truth: `src/spmkit/core/capabilities.json` "
                 "(generated view; do not edit by hand).")
    lines.append("")
    for record in records:
        cap = record["capability_id"]
        op = record["operation_id"]
        lines.append(f"## {cap}")
        lines.append("")
        lines.append(f"- operation_id: `{op}`")
        lines.append(f"- public_name: `{record['public_name']}`")
        lines.append(f"- public_import: `{record['public_import']}`")
        lines.append(f"- family: {record['family']}")
        lines.append(f"- maturity: {record['maturity']}")
        lines.append(f"- status: {record['status']}")
        ref = record["reference"]
        lines.append(f"- reference: {ref['software']} {ref['version']} "
                     f"({ref['name']})")
        lines.append(f"- evidence profile: `{ref['profile']}`")
        lines.append("")
        lines.append(f"- contract: {record['contract']}")
        lines.append("")
        lines.append("- semantics:")
        lines.append(f"  - mask: {record['mask_semantics']}")
        lines.append(f"  - ROI: {'yes' if record['roi_support'] else 'no'}")
        lines.append(f"  - NaN policy: {record['nan_policy']}")
        lines.append(f"  - border: {record['border_policy']}")
        lines.append(f"  - mutation: {record['mutation_policy']}")
        lines.append(f"  - result: {record['result_type']}")
        lines.append(f"  - units: {record['units']}")
        lines.append("")
        lines.append("- parameters:")
        for p in record["parameters"]:
            default = p["default"]
            default_s = "required" if not p["has_default"] else repr(default)
            extra = ""
            if p.get("bounds"):
                extra += f" bounds={p['bounds']}"
            if p.get("enum_values"):
                extra += f" values={p['enum_values']}"
            lines.append(f"  - `{p['name']}` ({p['kind']}, {default_s}"
                         f"{extra}) — {p['description']}")
        lines.append("")
        lines.append("- evidence:")
        for e in record["evidence"]:
            lines.append(f"  - `{e}`")
        lines.append("")
        if record["known_deviations"]:
            lines.append("- known deviations:")
            for d in record["known_deviations"]:
                lines.append(f"  - {d}")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    data = json.loads(LEDGER_JSON.read_text(encoding="utf-8"))
    records = sorted(data["capabilities"], key=lambda c: c["capability_id"])
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(render(records), encoding="utf-8")
    print(f"wrote {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

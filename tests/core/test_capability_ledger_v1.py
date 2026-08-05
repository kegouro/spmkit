"""Capability Ledger v1 tests.

Verifies the packaged capability ledger JSON: schema, deterministic
ordering, uniqueness, required fields, enum values, no Git/timestamp/
absolute-path metadata, evidence paths, import resolution, and byte-stable
Markdown regeneration.
"""

from __future__ import annotations

import importlib.resources
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_JSON = REPO_ROOT / "src" / "spmkit" / "core" / "capabilities.json"
LEDGER_MD = REPO_ROOT / "docs" / "parity" / "CAPABILITY_LEDGER.md"
GENERATOR = REPO_ROOT / "scripts" / "generate_capability_ledger.py"

REQUIRED_FIELDS = {
    "capability_id", "operation_id", "family", "public_name", "public_import",
    "aliases", "reference", "contract", "parameters", "result_type", "units",
    "mask_semantics", "roi_support", "nan_policy", "border_policy",
    "mutation_policy", "status", "maturity", "evidence", "known_deviations",
}
MATURITY = {"SPECIFIED", "SOFTWARE_VERIFIED", "NUMERICALLY_VERIFIED",
            "CROSS_VALIDATED", "PHYSICALLY_VALIDATED"}
STATUS = {"stable", "experimental", "deprecated"}
MASK = {"none", "include_exclude_ignore", "mask_input", "mask_output"}
NAN = {"reject", "propagate", "replace", "not_applicable"}
BORDER = {"clipped", "extend", "mirror", "periodic", "not_applicable"}
MUTATION = {"none", "returns_new", "in_place"}


def _load():
    return json.loads(LEDGER_JSON.read_text(encoding="utf-8"))


def test_schema_version_and_count() -> None:
    data = _load()
    assert data["schema_version"] == 1
    assert len(data["capabilities"]) == 17


def test_deterministic_ordering() -> None:
    data = _load()
    ids = [c["capability_id"] for c in data["capabilities"]]
    assert ids == sorted(ids)


def test_unique_ids_and_imports() -> None:
    data = _load()
    caps = [c["capability_id"] for c in data["capabilities"]]
    ops = [c["operation_id"] for c in data["capabilities"]]
    imps = [c["public_import"] for c in data["capabilities"]]
    assert len(set(caps)) == 17
    assert len(set(ops)) == 17
    assert len(set(imps)) == 17


def test_exact_derivative_registration_set() -> None:
    data = _load()
    caps = {c["capability_id"] for c in data["capabilities"]}
    ops = {c["operation_id"] for c in data["capabilities"]}
    assert {"IMG.FILTER.SOBEL_X", "IMG.FILTER.SOBEL_Y", "IMG.FILTER.PREWITT_X",
            "IMG.FILTER.PREWITT_Y", "IMG.FILTER.GRADIENT_MAGNITUDE",
            "IMG.FILTER.GRADIENT_DIRECTION"} <= caps
    assert {"img.filter.sobel_x", "img.filter.sobel_y", "img.filter.prewitt_x",
            "img.filter.prewitt_y", "img.filter.gradient_magnitude",
            "img.filter.gradient_direction"} <= ops
    # exactly six new capability records joined the original eleven
    assert len(caps) == 17 and len(ops) == 17


def test_required_fields_present() -> None:
    for c in _load()["capabilities"]:
        assert set(c.keys()) >= REQUIRED_FIELDS, c["capability_id"]


def test_valid_enum_values() -> None:
    for c in _load()["capabilities"]:
        assert c["maturity"] in MATURITY, c["capability_id"]
        assert c["status"] in STATUS, c["capability_id"]
        assert c["mask_semantics"] in MASK, c["capability_id"]
        assert c["nan_policy"] in NAN, c["capability_id"]
        assert c["border_policy"] in BORDER, c["capability_id"]
        assert c["mutation_policy"] in MUTATION, c["capability_id"]
        for p in c["parameters"]:
            assert p["kind"] in {"positional", "keyword_only"}
            assert p["has_default"] is not None
            if not p["has_default"]:
                assert p["default"] is None
            if p["required"]:
                assert not p["has_default"] or p["default"] is None


def test_no_git_or_timestamp_metadata() -> None:
    text = LEDGER_JSON.read_text(encoding="utf-8")
    for forbidden in ("commit", "timestamp", "generated_at", "branch", "head"):
        assert forbidden not in text, forbidden


def test_no_absolute_paths_and_no_reference_dependency() -> None:
    for c in _load()["capabilities"]:
        for e in c["evidence"]:
            assert not e.startswith("/"), e
            assert ".reference" not in e.split("/"), e
            assert ":" not in e and "\\" not in e, e


def test_aliases_explicit_lists() -> None:
    for c in _load()["capabilities"]:
        assert isinstance(c["aliases"], list)
        assert all(isinstance(a, str) for a in c["aliases"])


def test_all_evidence_paths_exist() -> None:
    for c in _load()["capabilities"]:
        for e in c["evidence"]:
            p = REPO_ROOT / e
            assert p.exists(), f"{c['capability_id']}: {e}"


def test_all_public_imports_resolve() -> None:
    import importlib
    for c in _load()["capabilities"]:
        module_name, attr = c["public_import"].split(":", 1)
        module = importlib.import_module(module_name)
        assert callable(getattr(module, attr)), c["public_import"]


def test_packaged_resource_accessible() -> None:
    resource = importlib.resources.files("spmkit.core").joinpath("capabilities.json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert len(data["capabilities"]) == 17


def test_markdown_regeneration_byte_identical() -> None:
    before = LEDGER_MD.read_bytes()
    subprocess.run(["python", str(GENERATOR)], check=True, capture_output=True)
    after = LEDGER_MD.read_bytes()
    assert after == before
    # the generated view must contain stable IDs and no timestamps
    text = after.decode("utf-8")
    assert "img.filter.rank" in text
    assert "timestamp" not in text and "commit" not in text


def test_json_serialization_deterministic() -> None:
    data = json.loads(LEDGER_JSON.read_text(encoding="utf-8"))
    a = json.dumps(data, indent=2, sort_keys=True)
    b = json.dumps(json.loads(a), indent=2, sort_keys=True)
    assert a == b

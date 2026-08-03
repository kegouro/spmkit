#!/usr/bin/env python3
"""Create and verify the content-addressed manual artifact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
MANIFEST_RELATIVE = "docs/manual/artifacts-manifest.json"
ARTIFACT_PATHS = (
    "docs/user-guide.md",
    "docs/user-guide.tex",
    "docs/user-guide.pdf",
)
EXPECTED_POLICY = {
    "identity": "content-addressed-manual-artifacts",
    "encoding": "UTF-8",
    "newline": "LF",
    "updater": "scripts/update_manual_provenance.py",
}
FORBIDDEN_PATH_PARTS = {"__pycache__", ".cache", ".git", "tmp"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"missing manual artifact: {relative}")
    return {"bytes": path.stat().st_size, "path": relative, "sha256": _sha256(path)}


def build_manifest(root: Path) -> dict[str, Any]:
    return {
        "artifacts": [_artifact_record(root, relative) for relative in ARTIFACT_PATHS],
        "policy": EXPECTED_POLICY,
        "schema_version": SCHEMA_VERSION,
    }


def render_manifest(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def manifest_path(root: Path) -> Path:
    return root / MANIFEST_RELATIVE


def write_manifest(root: Path) -> None:
    target = manifest_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = render_manifest(build_manifest(root))
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def _validate_relative_path(value: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, str):
        return [f"{field} must be a string"]
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or "\\" in value or any(part == ".." for part in parsed.parts):
        errors.append(f"{field} must be repository-relative")
    if any(part in FORBIDDEN_PATH_PARTS for part in parsed.parts):
        errors.append(f"{field} contains a forbidden local/cache path component")
    return errors


def _validate_manifest_shape(manifest: Any) -> list[str]:
    if not isinstance(manifest, dict):
        return ["manifest root must be an object"]
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if manifest.get("policy") != EXPECTED_POLICY:
        errors.append("policy does not match the canonical updater policy")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return [*errors, "artifacts must be a list"]
    seen: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_validate_relative_path(artifact.get("path"), f"{prefix}.path"))
        relative = artifact.get("path")
        if isinstance(relative, str):
            if relative in seen:
                errors.append(f"duplicate artifact path: {relative}")
            seen.add(relative)
        if not isinstance(artifact.get("bytes"), int) or artifact.get("bytes", -1) < 0:
            errors.append(f"{prefix}.bytes must be a non-negative integer")
        digest = artifact.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            errors.append(f"{prefix}.sha256 must be lowercase hexadecimal SHA-256")
    if seen != set(ARTIFACT_PATHS):
        errors.append("manifest artifact set does not match the canonical published set")
    return errors


def check_manifest(root: Path) -> list[str]:
    target = manifest_path(root)
    if not target.is_file():
        return [f"missing provenance manifest: {MANIFEST_RELATIVE}"]
    try:
        raw = target.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot parse provenance manifest: {exc}"]
    errors = _validate_manifest_shape(manifest)
    if errors:
        return errors
    if render_manifest(manifest) != raw:
        errors.append("manifest is not canonical UTF-8 JSON with an LF terminator")
    try:
        expected = build_manifest(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if manifest != expected:
        for expected_artifact, actual_artifact in zip(
            expected["artifacts"], manifest["artifacts"], strict=True
        ):
            if expected_artifact["path"] != actual_artifact["path"]:
                continue
            if expected_artifact["bytes"] != actual_artifact["bytes"]:
                errors.append(f"size mismatch: {expected_artifact['path']}")
            if expected_artifact["sha256"] != actual_artifact["sha256"]:
                errors.append(f"SHA-256 mismatch: {expected_artifact['path']}")
        if render_manifest(manifest) != render_manifest(expected):
            errors.append("manifest content is stale or not canonical JSON")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the canonical manifest")
    mode.add_argument("--check", action="store_true", help="verify the committed manifest")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.write:
            write_manifest(root)
            print(f"WROTE {manifest_path(root).relative_to(root)}")
            return 0
        errors = check_manifest(root)
    except OSError as exc:
        print(f"MANUAL PROVENANCE FAILED: {exc}")
        return 1
    if errors:
        print(f"MANUAL PROVENANCE FAILED: {len(errors)} problem(s)")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("MANUAL PROVENANCE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

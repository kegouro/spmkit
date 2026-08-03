from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts/update_manual_provenance.py"
ROOT = SCRIPT.parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("update_manual_provenance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative, content in (
        ("docs/user-guide.md", "manual\n"),
        ("docs/user-guide.tex", "tex\n"),
        ("docs/user-guide.pdf", b"pdf\n"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_write_is_deterministic_and_check_is_clean(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    first = _run(root, "--write")
    first_bytes = (root / "docs/manual/artifacts-manifest.json").read_bytes()
    second = _run(root, "--write")
    assert first.returncode == second.returncode == 0
    assert first_bytes == (root / "docs/manual/artifacts-manifest.json").read_bytes()
    assert _run(root, "--check").returncode == 0


@pytest.mark.parametrize("mutation", ["bytes", "size"])
def test_changed_artifact_fails(tmp_path: Path, mutation: str) -> None:
    root = _workspace(tmp_path)
    assert _run(root, "--write").returncode == 0
    artifact = root / "docs/user-guide.md"
    artifact.write_bytes(b"changed\n" if mutation == "bytes" else b"manual\nextra")
    result = _run(root, "--check")
    assert result.returncode == 1
    assert "mismatch" in result.stdout


def test_missing_and_stale_manifest_fail(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    assert _run(root, "--check").returncode == 1
    assert _run(root, "--write").returncode == 0
    (root / "docs/user-guide.tex").unlink()
    assert _run(root, "--check").returncode == 1


def test_malformed_and_extra_manifest_fail(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    manifest = root / "docs/manual/artifacts-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("not json\n", encoding="utf-8")
    assert _run(root, "--check").returncode == 1
    assert _run(root, "--write").returncode == 0
    data = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert _run(root, "--check").returncode == 1
    data["artifacts"].append({"path": "/absolute/secret", "bytes": 1, "sha256": "0" * 64})
    manifest.write_text(json.dumps(data), encoding="utf-8")
    result = _run(root, "--check")
    assert result.returncode == 1
    assert "repository-relative" in result.stdout


def test_check_does_not_modify_manifest(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    assert _run(root, "--write").returncode == 0
    manifest = root / "docs/manual/artifacts-manifest.json"
    before = manifest.stat().st_mtime_ns, manifest.read_bytes()
    assert _run(root, "--check").returncode == 0
    assert before == (manifest.stat().st_mtime_ns, manifest.read_bytes())


def test_repository_manifest_matches_real_artifacts() -> None:
    module = _module()
    assert module.check_manifest(ROOT) == []

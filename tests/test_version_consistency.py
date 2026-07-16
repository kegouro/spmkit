"""Tests that keep all active SPM-Kit version declarations synchronized."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

import spmkit


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_active_version_declarations_match() -> None:
    """Package, project metadata, and citation metadata must use one version."""

    pyproject_path = REPOSITORY_ROOT / "pyproject.toml"
    citation_path = REPOSITORY_ROOT / "CITATION.cff"

    with pyproject_path.open("rb") as handle:
        pyproject = tomllib.load(handle)

    with citation_path.open("r", encoding="utf-8") as handle:
        citation = yaml.safe_load(handle)

    project_version = str(pyproject["project"]["version"])
    runtime_version = str(spmkit.__version__)
    citation_version = str(citation["version"])

    assert runtime_version == project_version, (
        "src/spmkit/__init__.py and pyproject.toml disagree: "
        f"{runtime_version!r} != {project_version!r}"
    )

    assert citation_version == project_version, (
        "CITATION.cff and pyproject.toml disagree: "
        f"{citation_version!r} != {project_version!r}"
    )

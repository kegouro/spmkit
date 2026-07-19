from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).parents[1] / "src" / "spmkit" / "__init__.py"


def _load_version_module(monkeypatch: pytest.MonkeyPatch, resolver: object) -> ModuleType:
    core = ModuleType("spmkit.core")
    core.SPMChannel = object
    core.SPMData = object
    core.load = object
    monkeypatch.setitem(sys.modules, "spmkit.core", core)
    monkeypatch.setattr(importlib.metadata, "version", resolver)
    spec = importlib.util.spec_from_file_location("spmkit_version_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_comes_from_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_version_module(monkeypatch, lambda _: "9.9.9")

    assert module.__version__ == "9.9.9"


def test_version_falls_back_without_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    module = _load_version_module(monkeypatch, missing)

    assert module.__version__ == "0+unknown"

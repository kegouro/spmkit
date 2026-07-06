"""Tests del sistema de plugins: contratos, registry, inspect_any y load_any."""

from __future__ import annotations

from pathlib import Path

import pytest

from spmkit.core.io import inspect_any, load_any
from spmkit.core.models import ForceVolume, SPMData
from spmkit.core.plugins import (
    ENTRY_POINT_GROUP,
    PLUGIN_API_VERSION,
    DatasetInfo,
    Reader,
    reader_for,
    register_reader,
    supported_extensions,
)
from spmkit.core.plugins.contracts import Kind

_NID_DIR = Path(__file__).resolve().parents[2] / "reference" / "sample_files"


def test_contract_versioning() -> None:
    assert PLUGIN_API_VERSION == "1"
    assert ENTRY_POINT_GROUP == "spmkit.plugins.v1"


def test_builtin_readers_registered() -> None:
    exts = supported_extensions()
    for ext in (".nid", ".nhf", ".gwy", ".jpk-force"):
        assert ext in exts
    assert reader_for("x.nid") is not None
    assert reader_for("x.desconocido") is None


def test_custom_reader_conforms_and_registers() -> None:
    class DummyReader:
        extensions = (".dummy",)

        def inspect(self, path: str | Path) -> DatasetInfo:
            return DatasetInfo(path=Path(path), format="dummy", kinds=("image",))

        def load(self, path: str | Path, kind: Kind | None = None) -> object:
            return "cargado"

    dummy = DummyReader()
    assert isinstance(dummy, Reader)  # cumple el Protocol (runtime_checkable)
    register_reader(dummy)
    assert reader_for("a.dummy") is dummy
    assert load_any("a.dummy")[0] == "cargado"


def test_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        inspect_any("archivo.xyz")


@pytest.mark.skipif(not _NID_DIR.exists(), reason="samples .nid no disponibles (gitignored)")
def test_inspect_and_load_real_nid() -> None:
    nids = sorted(_NID_DIR.glob("*.nid"))
    if not nids:
        pytest.skip("sin .nid")
    # Un force-volume real: inspect debe declarar 'force' y load_any devolver ForceVolume.
    for nid in nids:
        info = inspect_any(nid)
        assert info.format == "nid"
        assert info.channels  # inspect leyó la cabecera
        if "force" in info.kinds:
            data, kind = load_any(nid, "force")
            assert kind == "force"
            assert isinstance(data, ForceVolume)
            break
    else:
        pytest.skip("ningún .nid de fuerza")


@pytest.mark.skipif(not _NID_DIR.exists(), reason="samples .nid no disponibles (gitignored)")
def test_load_any_image_nid() -> None:
    for nid in sorted(_NID_DIR.glob("*.nid")):
        info = inspect_any(nid)
        if "image" in info.kinds:
            data, kind = load_any(nid, "image")
            assert kind == "image" and isinstance(data, SPMData)
            return
    pytest.skip("ningún .nid de imagen")

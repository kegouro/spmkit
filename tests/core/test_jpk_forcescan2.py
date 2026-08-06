"""Tests FS-R1B: lector JPK ForceScan 2.0 (indirección ``lcd-info``).

Cubre: perfil directo (legacy), perfil ``lcd-info`` compartido, precedencia
(override local), referencias ausente/malformada, cadena cíclica, calibración
opcional ausente, cadena completa, propiedad compartida ausente, cadena no
soportada, unidades, determinismo del generador de fixtures, integración con
el loader público y no mutación.

Los fixtures los genera ``jpk_forcescan2_fixtures`` (independiente del lector):
los valores esperados se calculan a partir de los parámetros del fixture, no de
la salida del lector.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io import load_force, load_jpk_force
from spmkit.core.io.jpk import (
    JPK_CALIBRATION_CYCLE,
    JPK_INVALID_NUMBER,
    JPK_MISSING_PROPERTY,
    JPK_UNRESOLVED_LCD_INFO,
    JPK_UNSUPPORTED_CHAIN,
    JpkReaderError,
)
from spmkit.core.models import ForceVolume
from tests.jpk_forcescan2_fixtures import (
    write_complete_chain_jpk,
    write_cyclic_reference_jpk,
    write_direct_scaling_jpk,
    write_lcd_info_jpk,
    write_local_identical_jpk,
    write_local_override_jpk,
    write_malformed_reference_jpk,
    write_missing_optional_calibration_jpk,
    write_missing_reference_jpk,
    write_missing_shared_property_jpk,
    write_unsupported_chain_jpk,
)

#: Hashes deterministas de los fixtures canónicos (ver docstring del módulo).
FIXTURE_HASHES = {
    "direct": "031073b068673d88813a813ecaa9222bacf4edc13b44eac93bfae80b316dc182",
    "lcd_info": "ec75844a616e1f0ab4362049c324f8ff7ed720bf355a7499640c8b4683bdb8ba",
    "local_override": "f0c1ee284e8eab1de8bf2eebc6ebf13a119fd4dc6349e57e6b75e71c055dc144",
    "local_identical": "f56331fb3f32b9f052096a1b09ed5201fdf7befb4595432211f2ea28b71c52ad",
    "missing_reference": "f1007301e9f738bddb2e4843bf982180bb71844769a360274032c3d33fb16311",
    "malformed_reference": "ca9afd72f17835ffd8bd59cfe7b0505b7755181c7462411defaf138fed21ca73",
    "cyclic_reference": "1df9434fe08ac7d9b2462c607b22efbd6bceec6e3e0f0d5497ea052434c3312e",
    "missing_optional_calibration": (
        "5a8492f382e67628b36169e29133a86aeeccaaa7ca7683c060de72eaaabe74d1"
    ),
    "complete_chain": "fb417f51c7dfd3b2f1a46c568e7b82c4c14db859149b9d9e379061a03176978f",
    "missing_shared_property": "78273ce786022657bcca3ebbcba1f9f050ef06cab3ee1736826e2a36b2047c54",
    "unsupported_chain": "14de83d029da73fe81b0ce31c096f89cd084e9d693a7faf03eb5e87c6506bd76",
}

RAW_H = np.arange(8, dtype=np.int32) * 10  # [0, 10, ..., 70]
RAW_VD = np.arange(8, dtype=np.int32)  # [0, 1, ..., 7]

# Valores de las cadenas por defecto del generador (contrato de fixture).
H_MULT = 1.0e-9  # encoder height
VD_MULT = 1.0  # encoder vDeflection (V por unidad)
INVOLS = 2.0e-8  # slot distance
SPRING_K = 0.5  # slot force


def _expected_lcd_values() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Valores esperados calculados independientemente del lector (perfil lcd-info)."""
    h = RAW_H.astype(np.float64) * H_MULT  # encoder (V)
    h_m = h  # slot calibrated: x1.0 + 0.0 → m
    vd_v = RAW_VD.astype(np.float64) * VD_MULT
    d_m = vd_v * INVOLS
    f_n = d_m * SPRING_K
    return h_m, vd_v, d_m, f_n


def _write_fixture(tmp_path: Path, name: str) -> Path:
    """Escribe el fixture canónico ``name`` en tmp_path y devuelve la ruta."""
    path = tmp_path / f"{name}.jpk-force"
    _FIXTURE_WRITERS[name](path)
    return path


_FIXTURE_WRITERS = {
    "direct": lambda p: write_direct_scaling_jpk(
        p, RAW_H.astype(np.int16), RAW_VD.astype(np.int16)
    ),
    "lcd_info": lambda p: write_lcd_info_jpk(p, RAW_H, RAW_VD),
    "local_override": lambda p: write_local_override_jpk(p, RAW_H, RAW_VD),
    "local_identical": lambda p: write_local_identical_jpk(p, RAW_H, RAW_VD),
    "missing_reference": lambda p: write_missing_reference_jpk(p, RAW_H, RAW_VD),
    "malformed_reference": lambda p: write_malformed_reference_jpk(p, RAW_H, RAW_VD),
    "cyclic_reference": lambda p: write_cyclic_reference_jpk(p, RAW_H, RAW_VD),
    "missing_optional_calibration": lambda p: write_missing_optional_calibration_jpk(
        p, RAW_H, RAW_VD
    ),
    "complete_chain": lambda p: write_complete_chain_jpk(p, RAW_H, RAW_VD),
    "missing_shared_property": lambda p: write_missing_shared_property_jpk(p, RAW_H, RAW_VD),
    "unsupported_chain": lambda p: write_unsupported_chain_jpk(p, RAW_H, RAW_VD),
}


# ---------------------------------------------------------------------------
# Perfil directo (legacy) y perfil lcd-info: equivalencia de valores
# ---------------------------------------------------------------------------


def test_direct_profile_scaling_values(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "direct")
    curve = load_jpk_force(path)
    ext = curve.extend
    assert ext is not None and ext.state == "force_n"
    assert curve.metadata["profile"] == "direct"
    h_m, vd_v, d_m, f_n = _expected_lcd_values()
    assert np.allclose(ext.raw_height, h_m)
    assert np.allclose(ext.raw_deflection, vd_v)
    assert np.allclose(ext.deflection, d_m)
    assert np.allclose(ext.force, f_n)
    assert curve.calibration is not None
    assert curve.calibration.invols == pytest.approx(INVOLS)
    assert curve.calibration.spring_constant == pytest.approx(SPRING_K)


def test_lcd_info_profile_scaling_values(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "lcd_info")
    curve = load_jpk_force(path)
    ext = curve.extend
    assert ext is not None and ext.state == "force_n"
    assert curve.metadata["profile"] == "lcd-info"
    assert curve.segments[0].metadata["lcd_info"] == {"height": 0, "vDeflection": 1}
    h_m, vd_v, d_m, f_n = _expected_lcd_values()
    assert np.allclose(ext.raw_height, h_m)
    assert np.allclose(ext.raw_deflection, vd_v)
    assert np.allclose(ext.deflection, d_m)
    assert np.allclose(ext.force, f_n)
    assert curve.calibration is not None
    assert curve.calibration.invols == pytest.approx(INVOLS)
    assert curve.calibration.spring_constant == pytest.approx(SPRING_K)


def test_local_override_precedence(tmp_path: Path) -> None:
    """Claves directas del segmento ganan sobre la referencia lcd-info.

    Conflicto total: encoder local 9.0e-9 (shared 1.0e-9) Y slot local 2.0
    (shared 1.0): ninguna parte se fusiona desde shared-data.
    """
    path = _write_fixture(tmp_path, "local_override")
    curve = load_jpk_force(path)
    ext = curve.extend
    assert ext is not None
    # height usa SOLO valores locales: encoder 9.0e-9 y slot 2.0
    assert np.allclose(ext.raw_height, RAW_H.astype(np.float64) * 9.0e-9 * 2.0)
    # vDeflection no tiene claves directas → se resuelve por lcd-info
    assert curve.segments[0].metadata["lcd_info"] == {"height": None, "vDeflection": 1}
    assert np.allclose(ext.deflection, RAW_VD.astype(np.float64) * INVOLS)


def test_local_identical_to_shared_values(tmp_path: Path) -> None:
    """Claves directas idénticas a shared-data: mismo valor físico que el perfil puro."""
    p1 = _write_fixture(tmp_path, "local_identical")
    p2 = _write_fixture(tmp_path, "lcd_info")
    c1, c2 = load_jpk_force(p1), load_jpk_force(p2)
    assert np.array_equal(c1.extend.raw_height, c2.extend.raw_height)
    assert np.array_equal(c1.extend.force, c2.extend.force)
    # metadata: el canal height se tomó del segmento (perfil local)
    assert c1.segments[0].metadata["lcd_info"] == {"height": None, "vDeflection": 1}


def test_missing_local_encoder_offset_no_silent_fallback(tmp_path: Path) -> None:
    """Claves directas incompletas: fallo tipeado, NO fusión silenciosa con shared."""
    path = _write_fixture(tmp_path, "local_override")
    with zipfile.ZipFile(path) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}
    header = members["segments/0/segment-header.properties"].decode("utf-8")
    header = header.replace(
        "channel.height.data.encoder.scaling.offset=0.0",
        "channel.height.data.encoder.scaling.offset-missing",
    )
    header = header.replace("channel.height.data.encoder.scaling.offset-missing", "")
    # eliminar la clave offset (directa) del segmento 0
    lines = [
        line
        for line in header.splitlines()
        if not line.startswith("channel.height.data.encoder.scaling.offset=")
    ]
    members["segments/0/segment-header.properties"] = ("\n".join(lines) + "\n").encode()
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in members.items():
            zf.writestr(name, blob)
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_MISSING_PROPERTY
    assert "encoder.scaling.offset" in str(exc.value)


def test_malformed_local_number_raises(tmp_path: Path) -> None:
    """Multiplicador local malformado → JPK_INVALID_NUMBER (no fallback a shared)."""
    path = _write_fixture(tmp_path, "local_override")
    with zipfile.ZipFile(path) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}
    header = members["segments/0/segment-header.properties"].decode("utf-8")
    header = header.replace(
        "channel.height.data.encoder.scaling.multiplier=9.0E-9",
        "channel.height.data.encoder.scaling.multiplier=abc",
    )
    members["segments/0/segment-header.properties"] = header.encode("utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in members.items():
            zf.writestr(name, blob)
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_INVALID_NUMBER


# ---------------------------------------------------------------------------
# Fallos tipeados
# ---------------------------------------------------------------------------


def test_missing_reference_raises_typed(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "missing_reference")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_UNRESOLVED_LCD_INFO
    assert "lcd-info" in str(exc.value)


def test_malformed_reference_raises_typed(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "malformed_reference")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_UNRESOLVED_LCD_INFO


def test_cyclic_chain_raises_typed(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "cyclic_reference")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_CALIBRATION_CYCLE
    assert "cíclica" in str(exc.value)


def test_missing_shared_property_raises_typed(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "missing_shared_property")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_MISSING_PROPERTY
    # el mensaje identifica la cantidad semántica (encoder del canal height)
    assert "encoder.scaling.multiplier" in str(exc.value)


def test_unsupported_chain_raises_typed(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "unsupported_chain")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_UNSUPPORTED_CHAIN


def test_wrong_declared_unit_raises_typed(tmp_path: Path) -> None:
    """Unidad declarada incompatible con el rol del canal → fallo tipeado."""
    path = tmp_path / "wrong_unit.jpk-force"
    write_unsupported_chain_jpk(path, RAW_H, RAW_VD, defined=True, final_unit="V")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_UNSUPPORTED_CHAIN
    assert "unidad declarada incompatible" in str(exc.value)


def test_malformed_number_raises_typed(tmp_path: Path) -> None:
    """Multiplicador no numérico en shared-data → JPK_INVALID_NUMBER."""
    path = _write_fixture(tmp_path, "lcd_info")
    with zipfile.ZipFile(path) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}
    shared = members["shared-data/header.properties"].decode("utf-8")
    shared = shared.replace(
        "lcd-info.0.encoder.scaling.multiplier=1e-09",
        "lcd-info.0.encoder.scaling.multiplier=abc",
    )
    members["shared-data/header.properties"] = shared.encode("utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in members.items():
            zf.writestr(name, blob)
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(path)
    assert exc.value.code == JPK_INVALID_NUMBER


# ---------------------------------------------------------------------------
# Calibración opcional ausente (ausencia preservada, no corrupción)
# ---------------------------------------------------------------------------


def test_missing_optional_calibration_preserves_absence(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "missing_optional_calibration")
    curve = load_jpk_force(path)
    ext = curve.extend
    assert ext is not None
    assert ext.state == "deflection_m"
    assert ext.deflection is not None
    assert ext.force is None
    assert curve.calibration is None  # falta el slot force: no hay k → sin Calibration


# ---------------------------------------------------------------------------
# Cadena completa (nominal + calibrated, encoder + distance + force)
# ---------------------------------------------------------------------------


def test_complete_chain_full_calibration(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "complete_chain")
    curve = load_jpk_force(path)
    ext = curve.extend
    assert ext is not None and ext.state == "force_n"
    # height: crudo *1e-9 (V) → nominal (*-1.3e-7 + 1.5e-5) → calibrated (*0.78)
    h_v = RAW_H.astype(np.float64) * 1.0e-9
    expected_h = (h_v * -1.3e-7 + 1.5e-5) * 0.78
    assert np.allclose(ext.raw_height, expected_h)
    assert np.allclose(ext.deflection, RAW_VD.astype(np.float64) * INVOLS)
    assert np.allclose(ext.force, RAW_VD.astype(np.float64) * INVOLS * SPRING_K)
    assert curve.calibration is not None
    assert curve.calibration.invols == pytest.approx(INVOLS)
    assert curve.calibration.spring_constant == pytest.approx(SPRING_K)
    assert curve.calibration.method == "jpk_metadata"


# ---------------------------------------------------------------------------
# Integración con el loader público y no mutación
# ---------------------------------------------------------------------------


def test_public_loader_wraps_lcd_info_curve_in_volume(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "lcd_info")
    volume = load_force(path)
    assert isinstance(volume, ForceVolume)
    assert volume.n_curves == 1
    assert volume.grid_shape == (1, 1)
    curve = volume.curve(0)
    assert curve.calibration is not None


def test_reader_does_not_mutate_and_replays_deterministically(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, "complete_chain")
    c1 = load_jpk_force(path)
    c2 = load_jpk_force(path)
    ext1, ext2 = c1.extend, c2.extend
    assert np.array_equal(ext1.raw_height, ext2.raw_height)
    assert np.array_equal(ext1.force, ext2.force)
    # metadatos frescos por llamada (no se comparte el diccionario)
    assert c1.metadata is not c2.metadata
    assert c1.segments[0].metadata is not c2.segments[0].metadata
    # los diccionarios crudos de propiedades no se exponen ni mutan
    assert "lcd_info" in c1.segments[0].metadata


def test_typed_error_is_value_error(tmp_path: Path) -> None:
    """JpkReaderError sigue siendo ValueError: compatibilidad con llamadas previas."""
    path = _write_fixture(tmp_path, "missing_reference")
    with pytest.raises(ValueError):
        load_jpk_force(path)


def test_not_zip_raises_typed(tmp_path: Path) -> None:
    p = tmp_path / "notzip.jpk-force"
    p.write_bytes(b"this is not a zip archive at all")
    with pytest.raises(JpkReaderError) as exc:
        load_jpk_force(p)
    assert exc.value.code == "JPK_NOT_ZIP"


# ---------------------------------------------------------------------------
# Determinismo del generador de fixtures
# ---------------------------------------------------------------------------


def test_fixture_generation_is_deterministic(tmp_path: Path) -> None:
    """Tres directorios limpios → bytes idénticos; hashes fijos committeados."""
    blobs: dict[str, list[bytes]] = {}
    for i in range(3):
        d = tmp_path / f"dir{i}"
        d.mkdir()
        for name, writer in _FIXTURE_WRITERS.items():
            p = d / f"{name}.jpk-force"
            writer(p)
            blobs.setdefault(name, []).append(p.read_bytes())
    for name, copies in blobs.items():
        assert copies[0] == copies[1] == copies[2], f"fixture {name} no determinista"
        sha = hashlib.sha256(copies[0]).hexdigest()
        assert sha == FIXTURE_HASHES[name], f"fixture {name} cambió su hash"

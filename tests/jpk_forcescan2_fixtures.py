"""Independent deterministic JPK ``.jpk-force`` fixture generator (FS-R1B).

Produces minimal, deterministic JPK ZIP archives covering the reader contract
profiles. This module **never imports production parsing or resolution code**:
expected values in tests are computed from the fixture parameters, not from
reader output.

Determinism guarantees (used by the determinism tests):

- fixed ZIP member order (sorted member names);
- fixed ``ZipInfo`` timestamp (``FIXED_DATE_TIME``) and fixed compression;
- properties serialized with sorted keys and ``key=value`` lines;
- fixed small arrays with explicit big-endian dtypes.

Profiles (see module functions):

- direct scaling (legacy profile: scaling keys in the segment header);
- ``lcd-info`` shared scaling (JPK ForceScan 2.0 profile);
- local override (direct keys win over an ``lcd-info`` reference);
- missing reference; malformed reference; cyclic chain;
- missing shared property; unsupported chain (incl. wrong declared unit);
- missing optional calibration (absence preserved, not an error);
- complete height + deflection + spring-constant chain.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

#: Timestamp fijo de los miembros ZIP (determinismo).
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)

#: Cadena de conversión mínima del perfil directo (equivale a la cabecera
#: sintética de ``test_io_jpk.py``: height short 1.0e-9, vDeflection
#: encoder 1.0 V, distance 2.0e-8 m, force 0.5 N).
_DIRECT_HEIGHT_MULT = 1.0e-9
_DIRECT_INVOLS = 2.0e-8
_DIRECT_SPRING_K = 0.5


def props_bytes(props: dict[str, str]) -> bytes:
    """Serializa propiedades Java ``key=value`` con claves ordenadas (determinista)."""
    return "".join(f"{k}={v}\n" for k, v in sorted(props.items())).encode("ascii")


def write_zip(path: Path, members: dict[str, bytes]) -> None:
    """Escribe un ZIP determinista: orden fijo, fecha fija, deflate."""
    with zipfile.ZipFile(path, "w") as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, members[name])


def _segment_header_direct(name: str) -> dict[str, str]:
    """Perfil directo (legacy): claves de escalado en el propio segmento."""
    return {
        "force-segment-header.name.name": name,
        "channel.height.data.type": "short",
        "channel.height.data.encoder.scaling.multiplier": str(_DIRECT_HEIGHT_MULT),
        "channel.height.data.encoder.scaling.offset": "0.0",
        "channel.height.conversion-set.conversions.list": "calibrated",
        "channel.height.conversion-set.conversion.calibrated.scaling.multiplier": "1.0",
        "channel.height.conversion-set.conversion.calibrated.scaling.offset": "0.0",
        "channel.vDeflection.data.type": "short",
        "channel.vDeflection.data.encoder.scaling.multiplier": "1.0",
        "channel.vDeflection.data.encoder.scaling.offset": "0.0",
        "channel.vDeflection.conversion-set.conversions.list": "distance force",
        "channel.vDeflection.conversion-set.conversion.distance.scaling.multiplier": str(
            _DIRECT_INVOLS
        ),
        "channel.vDeflection.conversion-set.conversion.distance.scaling.offset": "0.0",
        "channel.vDeflection.conversion-set.conversion.force.scaling.multiplier": str(
            _DIRECT_SPRING_K
        ),
        "channel.vDeflection.conversion-set.conversion.force.scaling.offset": "0.0",
    }


def _lcd_info_record(
    channel: str,
    *,
    dtype: str = "integer-data",
    enc_mult: float,
    enc_offset: float,
    enc_unit: str = "V",
    base: str = "volts",
    slots: list[dict[str, object]],
) -> dict[str, str]:
    """Construye un registro ``lcd-info.{N}.*`` de shared-data (ForceScan 2.0)."""
    rec: dict[str, str] = {
        "type": dtype,
        "channel.type": "channel",
        "channel.name": channel,
        "unit.type": "metric-unit",
        "unit.unit": enc_unit,
        "conversion-set.conversions.list": " ".join(str(s["name"]) for s in slots),
        "conversion-set.conversions.default": str(slots[-1]["name"]),
        "conversion-set.conversions.base": base,
        "encoder.type": "signedinteger",
        "encoder.scaling.type": "linear",
        "encoder.scaling.style": "offsetmultiplier",
        "encoder.scaling.multiplier": str(enc_mult),
        "encoder.scaling.offset": str(enc_offset),
        "encoder.scaling.unit.type": "metric-unit",
        "encoder.scaling.unit.unit": enc_unit,
    }
    for s in slots:
        rec[f"conversion-set.conversion.{s['name']}.name"] = str(
            s.get("name", s["name"])
        ).capitalize()
        rec[f"conversion-set.conversion.{s['name']}.defined"] = str(
            s.get("defined", "true")
        ).lower()
        rec[f"conversion-set.conversion.{s['name']}.type"] = "simple"
        rec[f"conversion-set.conversion.{s['name']}.base-calibration-slot"] = str(s["base-slot"])
        rec[f"conversion-set.conversion.{s['name']}.calibration-slot"] = str(s["name"])
        rec[f"conversion-set.conversion.{s['name']}.scaling.type"] = "linear"
        rec[f"conversion-set.conversion.{s['name']}.scaling.style"] = "offsetmultiplier"
        rec[f"conversion-set.conversion.{s['name']}.scaling.multiplier"] = str(s["mult"])
        rec[f"conversion-set.conversion.{s['name']}.scaling.offset"] = str(s["offset"])
        rec[f"conversion-set.conversion.{s['name']}.scaling.unit.type"] = "metric-unit"
        rec[f"conversion-set.conversion.{s['name']}.scaling.unit.unit"] = str(s["unit"])
    return rec


def _lcd_info_defaults() -> dict[str, dict[str, str]]:
    """Registros lcd-info por defecto: cadenas equivalentes al perfil directo."""
    height = _lcd_info_record(
        "height",
        enc_mult=_DIRECT_HEIGHT_MULT,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {"name": "calibrated", "base-slot": "volts", "mult": 1.0, "offset": 0.0, "unit": "m"}
        ],
    )
    vd = _lcd_info_record(
        "vDeflection",
        enc_mult=1.0,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {
                "name": "distance",
                "base-slot": "volts",
                "mult": _DIRECT_INVOLS,
                "offset": 0.0,
                "unit": "m",
            },
            {
                "name": "force",
                "base-slot": "distance",
                "mult": _DIRECT_SPRING_K,
                "offset": 0.0,
                "unit": "N",
            },
        ],
    )
    return {"0": height, "1": vd}


def _lcd_info_segment_header(
    name: str,
    *,
    height_lcd: str = "0",
    vd_lcd: str = "1",
    num_points: int,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Cabecera de segmento ForceScan 2.0: referencias ``lcd-info.*`` + archivos."""
    h: dict[str, str] = {
        "force-segment-header.name.name": name,
        "channels.list": "height vDeflection",
        "channel.height.lcd-info.*": height_lcd,
        "channel.height.data.file.name": "channels/height.dat",
        "channel.height.data.file.format": "raw",
        "channel.height.data.num-points": str(num_points),
        "channel.vDeflection.lcd-info.*": vd_lcd,
        "channel.vDeflection.data.file.name": "channels/vDeflection.dat",
        "channel.vDeflection.data.file.format": "raw",
        "channel.vDeflection.data.num-points": str(num_points),
    }
    if overrides:
        h.update(overrides)
    return h


def _base_archive(
    path: Path,
    *,
    shared: dict[str, str],
    segment_headers: list[dict[str, str]],
    segments: list[dict[str, np.ndarray]],
    header_extra: dict[str, str] | None = None,
) -> None:
    """Ensambla un archivo .jpk-force determinista desde piezas ya construidas."""
    root = {"jpk-data-file": "spm-forcefile", "file-format-version": "2.0"}
    if header_extra:
        root.update(header_extra)
    members: dict[str, bytes] = {
        "header.properties": props_bytes(root),
        "shared-data/header.properties": props_bytes(shared),
    }
    for idx, (seg_header, channels) in enumerate(zip(segment_headers, segments, strict=True)):
        members[f"segments/{idx}/segment-header.properties"] = props_bytes(seg_header)
        for ch, arr in channels.items():
            members[f"segments/{idx}/channels/{ch}.dat"] = arr.astype(">i4").tobytes()
    write_zip(path, members)


def _segments_for(raw_h: np.ndarray, raw_vd: np.ndarray) -> list[dict[str, np.ndarray]]:
    return [
        {"height": raw_h.astype(np.int32), "vDeflection": raw_vd.astype(np.int32)},
        {"height": raw_h.astype(np.int32), "vDeflection": raw_vd.astype(np.int32)},
    ]


# ---------------------------------------------------------------------------
# Perfiles
# ---------------------------------------------------------------------------


def write_direct_scaling_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """1. Perfil directo (legacy): escalado en el segmento, datos int16."""
    members: dict[str, bytes] = {
        "header.properties": props_bytes({"jpk-data-file": "spm-forcefile"})
    }
    for idx, name in enumerate(("extend-spm", "retract-spm")):
        members[f"segments/{idx}/segment-header.properties"] = props_bytes(
            _segment_header_direct(name)
        )
        members[f"segments/{idx}/channels/height.dat"] = raw_h.astype(">i2").tobytes()
        members[f"segments/{idx}/channels/vDeflection.dat"] = raw_vd.astype(">i2").tobytes()
    write_zip(path, members)


def write_lcd_info_jpk(
    path: Path,
    raw_h: np.ndarray,
    raw_vd: np.ndarray,
    *,
    records: dict[str, dict[str, str]] | None = None,
    height_lcd: str = "0",
    vd_lcd: str = "1",
) -> None:
    """2. Perfil ForceScan 2.0: escalado vía ``lcd-info`` + shared-data, int32."""
    records = records or _lcd_info_defaults()
    shared: dict[str, str] = {"lcd-infos.count": str(len(records))}
    for idx, rec in records.items():
        for k, v in rec.items():
            shared[f"lcd-info.{idx}.{k}"] = v
    seg_headers = [
        _lcd_info_segment_header(
            "extend-spm", height_lcd=height_lcd, vd_lcd=vd_lcd, num_points=len(raw_h)
        ),
        _lcd_info_segment_header(
            "retract-spm", height_lcd=height_lcd, vd_lcd=vd_lcd, num_points=len(raw_h)
        ),
    ]
    _base_archive(
        path, shared=shared, segment_headers=seg_headers, segments=_segments_for(raw_h, raw_vd)
    )


def write_local_override_jpk(
    path: Path,
    raw_h: np.ndarray,
    raw_vd: np.ndarray,
    *,
    slot_mult: str = "2.0",
) -> None:
    """3. Override local: claves directas presentes Y referencia lcd-info.

    Las claves directas del segmento deben ganar (valores distintos a los de
    shared-data para poder distinguirlos), tanto en el encoder como en el slot
    de conversión (conflicto total: ningún valor se fusiona desde shared-data).
    """
    records = _lcd_info_defaults()
    shared: dict[str, str] = {"lcd-infos.count": str(len(records))}
    for idx, rec in records.items():
        for k, v in rec.items():
            shared[f"lcd-info.{idx}.{k}"] = v
    override = {
        # dtype explícito coherente con el payload int32 de este perfil
        "channel.height.data.type": "integer",
        "channel.height.data.encoder.scaling.multiplier": "9.0E-9",  # != 1.0E-9
        "channel.height.data.encoder.scaling.offset": "0.0",
        "channel.height.conversion-set.conversions.list": "calibrated",
        # slot en conflicto con shared-data (shared: 1.0)
        "channel.height.conversion-set.conversion.calibrated.scaling.multiplier": slot_mult,
        "channel.height.conversion-set.conversion.calibrated.scaling.offset": "0.0",
    }
    seg_headers = [
        _lcd_info_segment_header("extend-spm", num_points=len(raw_h), overrides=override),
        _lcd_info_segment_header("retract-spm", num_points=len(raw_h), overrides=override),
    ]
    _base_archive(
        path, shared=shared, segment_headers=seg_headers, segments=_segments_for(raw_h, raw_vd)
    )


def write_local_identical_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """3b. Claves directas IDÉNTICAS a shared-data + referencia lcd-info.

    El resultado debe ser el mismo valor físico que el perfil compartido puro
    (la precedencia local no altera el número cuando ambos coinciden).
    """
    records = _lcd_info_defaults()
    shared: dict[str, str] = {"lcd-infos.count": str(len(records))}
    for idx, rec in records.items():
        for k, v in rec.items():
            shared[f"lcd-info.{idx}.{k}"] = v
    override = {
        "channel.height.data.type": "integer",
        # == shared 1.0e-9
        "channel.height.data.encoder.scaling.multiplier": str(_DIRECT_HEIGHT_MULT),
        "channel.height.data.encoder.scaling.offset": "0.0",
        "channel.height.conversion-set.conversions.list": "calibrated",
        # == shared
        "channel.height.conversion-set.conversion.calibrated.scaling.multiplier": "1.0",
        "channel.height.conversion-set.conversion.calibrated.scaling.offset": "0.0",
    }
    seg_headers = [
        _lcd_info_segment_header("extend-spm", num_points=len(raw_h), overrides=override),
        _lcd_info_segment_header("retract-spm", num_points=len(raw_h), overrides=override),
    ]
    _base_archive(
        path, shared=shared, segment_headers=seg_headers, segments=_segments_for(raw_h, raw_vd)
    )


def write_missing_reference_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """4. Referencia fuera de rango: ``lcd-info.*=5`` con solo 2 registros."""
    write_lcd_info_jpk(path, raw_h, raw_vd, height_lcd="5")


def write_malformed_reference_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """5. Referencia malformada: ``lcd-info.*=abc``."""
    write_lcd_info_jpk(path, raw_h, raw_vd, height_lcd="abc")


def write_cyclic_reference_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """6. Cadena cíclica: el slot ``calibrated`` se referencia a sí mismo."""
    height = _lcd_info_record(
        "height",
        enc_mult=_DIRECT_HEIGHT_MULT,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {"name": "nominal", "base-slot": "volts", "mult": 1.0, "offset": 0.0, "unit": "m"},
            # auto-referencia: calibrated.base-calibration-slot == calibrated
            {
                "name": "calibrated",
                "base-slot": "calibrated",
                "mult": 0.78,
                "offset": 0.0,
                "unit": "m",
            },
        ],
    )
    vd = _lcd_info_defaults()["1"]
    write_lcd_info_jpk(path, raw_h, raw_vd, records={"0": height, "1": vd})


def write_missing_optional_calibration_jpk(
    path: Path, raw_h: np.ndarray, raw_vd: np.ndarray
) -> None:
    """7. Calibración opcional ausente: vDeflection sin slot ``force``.

    El archivo es válido: la ausencia del slot force se preserva (state
    ``deflection_m``, force ``None``, calibration ``None``), no es corrupción.
    """
    vd = _lcd_info_record(
        "vDeflection",
        enc_mult=1.0,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {
                "name": "distance",
                "base-slot": "volts",
                "mult": _DIRECT_INVOLS,
                "offset": 0.0,
                "unit": "m",
            }
        ],
    )
    records = {"0": _lcd_info_defaults()["0"], "1": vd}
    write_lcd_info_jpk(path, raw_h, raw_vd, records=records)


def write_complete_chain_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """8. Cadena completa: height nominal+calibrated, vDeflection encoder+distance+force.

    Los valores de la cadena nominal→calibrated son arbitrarios pero explícitos
    (mult nominal 1.3e-7, offset 1.5e-5; mult calibrated 0.78).
    """
    height = _lcd_info_record(
        "height",
        enc_mult=_DIRECT_HEIGHT_MULT,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {
                "name": "nominal",
                "base-slot": "volts",
                "mult": -1.3e-7,
                "offset": 1.5e-5,
                "unit": "m",
            },
            {
                "name": "calibrated",
                "base-slot": "nominal",
                "mult": 0.78,
                "offset": 0.0,
                "unit": "m",
            },
        ],
    )
    records = {"0": height, "1": _lcd_info_defaults()["1"]}
    write_lcd_info_jpk(path, raw_h, raw_vd, records=records)


def write_missing_shared_property_jpk(path: Path, raw_h: np.ndarray, raw_vd: np.ndarray) -> None:
    """9. Registro lcd-info presente pero sin ``encoder.scaling.multiplier``."""
    height = _lcd_info_record(
        "height",
        enc_mult=_DIRECT_HEIGHT_MULT,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=[
            {"name": "calibrated", "base-slot": "volts", "mult": 1.0, "offset": 0.0, "unit": "m"}
        ],
    )
    del height["encoder.scaling.multiplier"]
    records = {"0": height, "1": _lcd_info_defaults()["1"]}
    write_lcd_info_jpk(path, raw_h, raw_vd, records=records)


def write_unsupported_chain_jpk(
    path: Path,
    raw_h: np.ndarray,
    raw_vd: np.ndarray,
    *,
    defined: bool = False,
    final_unit: str | None = "V",
) -> None:
    """10. Cadena no soportada: slot ``user`` no definido, o unidad declarada ilegal.

    Con ``defined=False`` el slot está declarado pero no calibrado; con
    ``final_unit`` distinto de ``m`` la unidad final declarada es incompatible
    con el rol del canal height.
    """
    slots: list[dict[str, object]] = [
        {
            "name": "user",
            "base-slot": "volts",
            "mult": 1.0,
            "offset": 0.0,
            "unit": final_unit or "V",
            "defined": defined,
        }
    ]
    height = _lcd_info_record(
        "height",
        enc_mult=_DIRECT_HEIGHT_MULT,
        enc_offset=0.0,
        enc_unit="V",
        base="volts",
        slots=slots,
    )
    records = {"0": height, "1": _lcd_info_defaults()["1"]}
    write_lcd_info_jpk(path, raw_h, raw_vd, records=records)

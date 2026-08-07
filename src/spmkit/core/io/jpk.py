"""Lector de curvas de fuerza JPK / Bruker (``.jpk-force``).

Un ``.jpk-force`` es un archivo **ZIP**. Se soportan dos perfiles de metadatos:

1. **Perfil directo (legacy)**: las claves de escalado viven en el propio
   segmento (``channel.height.data.encoder.scaling.multiplier``, etc.),
   como en las muestras derivadas de ``AFM-analysis/afmformats``::

       header.properties
       segments/0/segment-header.properties          # extend (approach)
       segments/0/channels/height.dat                # enteros crudos big-endian
       segments/0/channels/vDeflection.dat
       segments/1/...                                 # retract

2. **Perfil ForceScan 2.0 (``lcd-info``)**: la cabecera de segmento solo
   referencia registros de calibración que viven en
   ``shared-data/header.properties`` mediante la clave
   ``channel.{name}.lcd-info.*={index}`` (el ``*`` forma parte de la clave)::

       shared-data/header.properties                  # lcd-infos.count + lcd-info.{i}.*
       segments/0/segment-header.properties           # channel.height.lcd-info.*=1, etc.
       segments/0/channels/height.dat                 # int32 big-endian

   El registro ``lcd-info.{index}`` define: el tipo de dato crudo
   (``type=integer-data`` → int32), el escalado del encoder (crudo → voltios)
   y la cadena de conversión ``conversion-set.conversion.{slot}.*``
   (``valor·multiplier + offset`` por slot, en el orden de
   ``conversions.list``, partiendo de ``conversions.base``).

Cada canal se convierte a unidades físicas con la **cascada de "calibration
slots"**:

* ``vDeflection``: crudo → encoder (V) → ``distance`` (m, multiplier = InVOLS)
  → ``force`` (N, multiplier = k). La calibración (InVOLS, k) vive en el archivo.
* ``height``: crudo → encoder (V) → ``nominal`` → ``calibrated`` (m).

Las claves explícitas del segmento (perfil directo) **ganan** sobre cualquier
referencia ``lcd-info`` cuando ambas coexisten (override local).

Los fallos son errores tipeados :class:`JpkReaderError` (subclase de
``ValueError``) con un código máquina legible. Nunca se sustituye una
calibración adivinada: una cadena incompleta o no soportada es un fallo
tipeado, no una matriz sin unidades.
"""

from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from spmkit.core.models import Calibration, CalState, ForceCurve, ForceSegment, SegmentType

#: Códigos de fallo tipeado del lector JPK.
JPK_NOT_ZIP = "JPK_NOT_ZIP"
JPK_NO_SEGMENTS = "JPK_NO_SEGMENTS"
JPK_MISSING_PROPERTY = "JPK_MISSING_PROPERTY"
JPK_UNRESOLVED_LCD_INFO = "JPK_UNRESOLVED_LCD_INFO"
JPK_CALIBRATION_CYCLE = "JPK_CALIBRATION_CYCLE"
JPK_INVALID_NUMBER = "JPK_INVALID_NUMBER"
JPK_UNSUPPORTED_CHAIN = "JPK_UNSUPPORTED_CHAIN"

_SEG_RE = re.compile(r"segments/(\d+)/segment-header\.properties$")

#: ``data.type`` de JPK → dtype numpy (big-endian, formato Java).
_DTYPES = {
    "short": ">i2",
    "integer": ">i4",
    "int": ">i4",
    "long": ">i8",
    "float": ">f4",
    "double": ">f8",
}

#: Tipo de registro ``lcd-info`` → dtype numpy (perfil ForceScan 2.0).
_LCD_TYPES = {
    "integer-data": ">i4",
    "short-data": ">i2",
    "double-data": ">f8",
    "float-data": ">f4",
}


class JpkReaderError(ValueError):
    """Fallo tipeado del lector JPK con código máquina legible."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _ChannelScaling:
    """Escalado efectivo de un canal: encoder + slots de conversión ordenados.

    Es un conjunto **efectivo** (ya resuelto): o bien viene del perfil directo
    (``lcd_info=None``), o bien de un registro ``lcd-info.{index}`` de
    shared-data (``lcd_info=index``). No muta los diccionarios crudos.
    """

    dtype: str  # dtype numpy (p. ej. ">i4")
    enc_mult: float
    enc_offset: float
    enc_unit: str | None
    #: (slot, multiplier, offset, unidad declarada o None) en orden de la cadena.
    slots: tuple[tuple[str, float, float, str | None], ...]
    lcd_info: int | None


def _parse_properties(raw: bytes) -> dict[str, str]:
    """Parsea un ``.properties`` de Java (``clave=valor``, ``#`` comentarios)."""
    props: dict[str, str] = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")) or "=" not in line:
            continue
        key, _, value = line.partition("=")
        props[key.strip()] = value.strip()
    return props


def _float_prop(props: dict[str, str], key: str, *, detail: str = "") -> float:
    """Lee y valida un número de propiedades; fallo tipeado si falta o es inválido."""
    if key not in props:
        raise JpkReaderError(
            JPK_MISSING_PROPERTY,
            f"Archivo .jpk-force corrupto o incompleto (falta '{key}'): {detail}".strip(),
        )
    raw = props[key]
    try:
        value = float(raw)
    except ValueError:
        raise JpkReaderError(
            JPK_INVALID_NUMBER,
            f"Archivo .jpk-force con valor numérico malformado: '{key}={raw!r}' ({detail})".strip(),
        ) from None
    if not math.isfinite(value):
        raise JpkReaderError(
            JPK_INVALID_NUMBER,
            f"Archivo .jpk-force con valor numérico no finito: '{key}={raw!r}' ({detail})".strip(),
        )
    return value


def _parse_lcd_info_reference(value: str, channel: str) -> int:
    """Valida el valor de ``channel.{c}.lcd-info.*`` → índice entero."""
    try:
        index = int(value)
    except ValueError:
        raise JpkReaderError(
            JPK_UNRESOLVED_LCD_INFO,
            f"Archivo .jpk-force con referencia lcd-info malformada "
            f"(channel.{channel}.lcd-info.*={value!r}): se esperaba un índice entero",
        ) from None
    if index < 0:
        raise JpkReaderError(
            JPK_UNRESOLVED_LCD_INFO,
            f"Archivo .jpk-force con referencia lcd-info negativa "
            f"(channel.{channel}.lcd-info.*={value!r})",
        )
    return index


def _resolve_lcd_info_reference(
    seg_props: dict[str, str], shared: dict[str, str], channel: str
) -> tuple[int, str]:
    """Resuelve ``channel.{c}.lcd-info.*`` → ``(index, prefijo 'lcd-info.{i}.')``.

    Fallos tipeados: referencia ausente (perfil sin escalado directo ni
    referencia), malformada, o registro inexistente en shared-data.
    """
    pfx = f"channel.{channel}"
    ref = seg_props.get(f"{pfx}.lcd-info.*")
    if ref is None:
        raise JpkReaderError(
            JPK_MISSING_PROPERTY,
            f"Archivo .jpk-force corrupto o incompleto (falta "
            f"'{pfx}.data.encoder.scaling.multiplier'): el segmento no tiene "
            f"escalado directo ni referencia '{pfx}.lcd-info.*'",
        )
    index = _parse_lcd_info_reference(ref, channel)
    rec = f"lcd-info.{index}."
    if f"{rec}channel.name" not in shared:
        raise JpkReaderError(
            JPK_UNRESOLVED_LCD_INFO,
            f"Archivo .jpk-force con referencia lcd-info sin resolver: "
            f"{pfx}.lcd-info.*={ref} pero no existe el registro '{rec.rstrip('.')}' "
            f"en shared-data/header.properties",
        )
    return index, rec


def _resolve_calibration_chain(
    shared: dict[str, str], rec: str, channel: str
) -> tuple[tuple[str, float, float, str | None], ...]:
    """Valida y ordena la cadena ``conversion-set`` de un registro lcd-info.

    Reglas (semántica demostrada por los archivos ForceScan 2.0):

    * el primer slot cuelga de ``conversions.base`` (pseudo-slot, p. ej.
      ``volts``) o de otro slot; cada slot posterior cuelga del anterior;
    * un slot que se referencia a sí mismo o a un slot posterior es una
      **cadena cíclica** (fallo tipeado);
    * un slot declarado ``defined=false`` no puede calibrar (fallo tipeado;
      nunca se sustituye un valor adivinado);
    * los multipliers/offsets deben ser numéricos finitos.
    """
    slots_list = shared.get(f"{rec}conversion-set.conversions.list", "").split()
    if not slots_list:
        raise JpkReaderError(
            JPK_UNSUPPORTED_CHAIN,
            f"Archivo .jpk-force con cadena de calibración vacía para el canal "
            f"{channel} (conversions.list ausente en '{rec.rstrip('.')}')",
        )
    base = shared.get(f"{rec}conversion-set.conversions.base")
    ordered: list[tuple[str, float, float, str | None]] = []
    for i, slot in enumerate(slots_list):
        sp = f"{rec}conversion-set.conversion.{slot}."
        defined = shared.get(f"{sp}defined")
        if defined is not None and defined.strip().lower() == "false":
            raise JpkReaderError(
                JPK_UNSUPPORTED_CHAIN,
                f"Archivo .jpk-force con slot '{slot}' del canal {channel} no "
                f"definido (defined=false): no se puede calibrar sin inventar valores",
            )
        slot_base = shared.get(f"{sp}base-calibration-slot")
        if slot_base is not None and slot_base in slots_list and slots_list.index(slot_base) >= i:
            raise JpkReaderError(
                JPK_CALIBRATION_CYCLE,
                f"Archivo .jpk-force con cadena de calibración cíclica para el "
                f"canal {channel}: el slot '{slot}' se referencia a '{slot_base}'",
            )
        if slot_base is not None and slot_base not in slots_list and slot_base != base:
            raise JpkReaderError(
                JPK_UNSUPPORTED_CHAIN,
                f"Archivo .jpk-force con slot '{slot}' del canal {channel} "
                f"referenciando una base desconocida '{slot_base}'",
            )
        mult = _float_prop(
            shared, f"{sp}scaling.multiplier", detail=f"canal {channel}, slot {slot}"
        )
        offset = _float_prop(shared, f"{sp}scaling.offset", detail=f"canal {channel}, slot {slot}")
        unit = shared.get(f"{sp}scaling.unit.unit")
        ordered.append((slot, mult, offset, unit))
    return tuple(ordered)


def _resolve_channel_scaling(
    seg_props: dict[str, str], shared: dict[str, str], channel: str
) -> _ChannelScaling:
    """Resuelve el escalado efectivo de un canal: directo gana, si no lcd-info.

    Precedencia: si el segmento trae las claves directas
    (``channel.{c}.data.encoder.scaling.*``) se usan esas (perfil legacy); solo
    si faltan se sigue la indirección ``channel.{c}.lcd-info.*`` hacia
    shared-data (perfil ForceScan 2.0).
    """
    pfx = f"channel.{channel}"
    direct_key = f"{pfx}.data.encoder.scaling.multiplier"
    if direct_key in seg_props:
        dtype = _DTYPES.get(seg_props.get(f"{pfx}.data.type", "short"), ">i2")
        enc_mult = _float_prop(seg_props, direct_key, detail=f"canal {channel}")
        enc_offset = _float_prop(
            seg_props, f"{pfx}.data.encoder.scaling.offset", detail=f"canal {channel}"
        )
        slots_list = seg_props.get(f"{pfx}.conversion-set.conversions.list", "").split()
        direct_slots: list[tuple[str, float, float, str | None]] = []
        for slot in slots_list:
            sp = f"{pfx}.conversion-set.conversion.{slot}."
            mult = _float_prop(
                seg_props, f"{sp}scaling.multiplier", detail=f"canal {channel}, slot {slot}"
            )
            offset = _float_prop(
                seg_props, f"{sp}scaling.offset", detail=f"canal {channel}, slot {slot}"
            )
            direct_slots.append((slot, mult, offset, None))
        return _ChannelScaling(dtype, enc_mult, enc_offset, None, tuple(direct_slots), None)

    index, rec = _resolve_lcd_info_reference(seg_props, shared, channel)
    declared = seg_props.get(f"{pfx}.data.type")
    if declared is not None:
        dtype = _DTYPES.get(declared, ">i2")
    else:
        lcd_type = shared.get(f"{rec}type")
        if lcd_type not in _LCD_TYPES:
            raise JpkReaderError(
                JPK_UNSUPPORTED_CHAIN,
                f"Archivo .jpk-force sin tipo de dato decodificable para el canal "
                f"{channel} (lcd-info.{index}.type={lcd_type!r})",
            )
        dtype = _LCD_TYPES[lcd_type]
    enc_mult = _float_prop(shared, f"{rec}encoder.scaling.multiplier", detail=f"canal {channel}")
    enc_offset = _float_prop(shared, f"{rec}encoder.scaling.offset", detail=f"canal {channel}")
    enc_unit = shared.get(f"{rec}encoder.scaling.unit.unit")
    slots = _resolve_calibration_chain(shared, rec, channel)
    return _ChannelScaling(dtype, enc_mult, enc_offset, enc_unit, slots, index)


def _require_declared_unit(unit: str | None, expected: str, channel: str, slot: str) -> None:
    """Unidad declarada incompatible con el rol del canal → fallo tipeado."""
    if unit is not None and unit != expected:
        raise JpkReaderError(
            JPK_UNSUPPORTED_CHAIN,
            f"Archivo .jpk-force con unidad declarada incompatible para el canal "
            f"{channel} (slot '{slot}'): {unit!r} (se esperaba {expected!r})",
        )


def _validate_role_units(scaling: _ChannelScaling, channel: str) -> None:
    """Verifica las unidades declaradas de los slots según el rol del canal.

    La unidad de salida del canal height debe ser ``m``; los slots
    ``distance``/``force`` de vDeflection deben ser ``m``/``N``. Si una clave
    de unidad no está declarada se preserva la ausencia (perfil legacy no
    declara unidades).
    """
    if channel == "height":
        if scaling.slots:
            slot, _m, _o, unit = scaling.slots[-1]
            _require_declared_unit(unit, "m", channel, slot)
    else:
        for slot, _m, _o, unit in scaling.slots:
            if slot == "distance":
                _require_declared_unit(unit, "m", channel, slot)
            if slot == "force":
                _require_declared_unit(unit, "N", channel, slot)


def _read_channel_raw(
    zf: zipfile.ZipFile, seg: int, channel: str, scaling: _ChannelScaling
) -> np.ndarray:
    """Lee un canal ``.dat`` con el dtype resuelto del perfil."""
    blob = zf.read(f"segments/{seg}/channels/{channel}.dat")
    return np.frombuffer(blob, dtype=scaling.dtype)


def _channel_value(
    raw: np.ndarray, scaling: _ChannelScaling, stop_after: str | None = None
) -> np.ndarray:
    """Aplica encoder + slots del escalado resuelto hasta ``stop_after``.

    ``stop_after="encoder"`` devuelve la salida del encoder (voltios); ``None``
    aplica toda la cadena (unidad física final).
    """
    value = raw.astype(np.float64) * scaling.enc_mult + scaling.enc_offset
    if stop_after == "encoder":
        return value
    for slot, mult, offset, _unit in scaling.slots:
        value = value * mult + offset
        if slot == stop_after:
            return value
    return value


def _slot_multiplier(scaling: _ChannelScaling, slot: str) -> float:
    """Multiplicador de un slot de la cadena (p. ej. InVOLS, k)."""
    for name, mult, _offset, _unit in scaling.slots:
        if name == slot:
            return mult
    raise KeyError(f"channel.vDeflection.conversion-set.conversion.{slot}")  # noqa: TRY003


def _segment_kind(props: dict[str, str], index: int) -> tuple[SegmentType, str]:
    """Deduce ``(segment_type, direction)`` del nombre del segmento (o su índice)."""
    name = props.get("force-segment-header.name.name", "").lower()
    if "extend" in name or "approach" in name:
        return "extend", "approach"
    if "retract" in name or "pull" in name:
        return "retract", "retract"
    if "pause" in name or "delay" in name or "constant" in name:
        return "pause", "static"
    return ("extend", "approach") if index % 2 == 0 else ("retract", "retract")


def load_jpk_force(path: str | Path) -> ForceCurve:
    """Lee un ``.jpk-force`` y devuelve un :class:`ForceCurve` calibrado.

    Soporta el perfil directo (legacy) y el perfil ForceScan 2.0 con
    indirección ``lcd-info`` hacia ``shared-data/header.properties``.

    Raises:
        JpkReaderError: fallo tipeado (subclase de ``ValueError``) con código
            ``JPK_NOT_ZIP``/``JPK_NO_SEGMENTS``/``JPK_MISSING_PROPERTY``/
            ``JPK_UNRESOLVED_LCD_INFO``/``JPK_CALIBRATION_CYCLE``/
            ``JPK_INVALID_NUMBER``/``JPK_UNSUPPORTED_CHAIN``.
    """
    path = Path(path)
    try:
        return _load_jpk_force(path)
    except zipfile.BadZipFile as exc:
        raise JpkReaderError(
            JPK_NOT_ZIP, f"Archivo .jpk-force no es un ZIP válido (¿corrupto?): {path}"
        ) from exc
    except KeyError as exc:
        raise JpkReaderError(
            JPK_MISSING_PROPERTY,
            f"Archivo .jpk-force corrupto o incompleto (falta {exc}): {path}",
        ) from exc


def _load_jpk_force(path: Path) -> ForceCurve:
    with zipfile.ZipFile(path) as zf:
        seg_ids = sorted({int(m.group(1)) for name in zf.namelist() if (m := _SEG_RE.search(name))})
        if not seg_ids:
            raise JpkReaderError(
                JPK_NO_SEGMENTS, f"No es un .jpk-force válido (sin segmentos): {path}"
            )

        # shared-data se lee UNA vez por archivo (perfil ForceScan 2.0).
        shared = (
            _parse_properties(zf.read("shared-data/header.properties"))
            if "shared-data/header.properties" in zf.namelist()
            else {}
        )

        segments: list[ForceSegment] = []
        invols: float | None = None
        spring_k: float | None = None
        profile = "direct"

        for seg in seg_ids:
            seg_props = _parse_properties(zf.read(f"segments/{seg}/segment-header.properties"))
            kind, direction = _segment_kind(seg_props, seg)

            h_scaling = _resolve_channel_scaling(seg_props, shared, "height")
            v_scaling = _resolve_channel_scaling(seg_props, shared, "vDeflection")
            _validate_role_units(h_scaling, "height")
            _validate_role_units(v_scaling, "vDeflection")
            if h_scaling.lcd_info is not None or v_scaling.lcd_info is not None:
                profile = "lcd-info"

            raw_h = _read_channel_raw(zf, seg, "height", h_scaling)
            raw_vd = _read_channel_raw(zf, seg, "vDeflection", v_scaling)
            height_m = _channel_value(raw_h, h_scaling)
            volts = _channel_value(raw_vd, v_scaling, stop_after="encoder")

            slot_names = [s[0] for s in v_scaling.slots]
            deflection = force = separation = None
            state: CalState = "raw_v"
            if "distance" in slot_names:
                deflection = _channel_value(raw_vd, v_scaling, stop_after="distance")
                separation = height_m - deflection
                invols = _slot_multiplier(v_scaling, "distance")
                state = "deflection_m"
            if "force" in slot_names:
                force = _channel_value(raw_vd, v_scaling, stop_after="force")
                spring_k = _slot_multiplier(v_scaling, "force")
                state = "force_n"

            meta: dict = {"num_points": int(raw_h.size)}
            if h_scaling.lcd_info is not None or v_scaling.lcd_info is not None:
                meta["lcd_info"] = {"height": h_scaling.lcd_info, "vDeflection": v_scaling.lcd_info}

            segments.append(
                ForceSegment(
                    segment_type=kind,
                    direction=direction,
                    raw_height=height_m,
                    raw_deflection=volts,
                    deflection=deflection,
                    force=force,
                    separation=separation,
                    state=state,
                    metadata=meta,
                )
            )

        calibration = None
        if invols is not None and spring_k is not None:
            calibration = Calibration(
                invols=invols,
                spring_constant=spring_k,
                method="jpk_metadata",
                provenance={"source": path.name, "profile": profile},
            )

        return ForceCurve(
            segments=tuple(segments),
            calibration=calibration,
            metadata={"format": "jpk-force", "source_path": str(path), "profile": profile},
        )

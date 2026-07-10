"""Lector de curvas de fuerza JPK / Bruker (``.jpk-force``).

Un ``.jpk-force`` es un archivo **ZIP** con esta estructura (verificada con datos
reales del dataset abierto ``AFM-analysis/afmformats``)::

    header.properties
    segments/0/segment-header.properties          # extend (approach)
    segments/0/channels/height.dat                # enteros crudos big-endian
    segments/0/channels/vDeflection.dat
    segments/1/...                                 # retract

Cada canal se convierte a unidades físicas con una **cascada de "calibration
slots"**, cada uno ``valor·multiplier + offset``, en el orden de
``conversion-set.conversions.list``:

* ``vDeflection``: ``short`` → encoder (V) → ``distance`` (m, multiplier = InVOLS)
  → ``force`` (N, multiplier = k). La calibración (InVOLS, k) vive en el archivo.
* ``height``: ``short`` → encoder (V) → ``nominal`` → ``calibrated`` (m).

Devuelve un :class:`ForceCurve` con segmentos extend/retract ya calibrados.
Referencia de implementación: ``afmformats``/``nanite``/``PyJibe`` (Paul Müller).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np

from spmkit.core.models import Calibration, CalState, ForceCurve, ForceSegment, SegmentType

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


def _read_channel_raw(
    zf: zipfile.ZipFile, seg: int, channel: str, props: dict[str, str]
) -> np.ndarray:
    """Lee un canal ``.dat`` como enteros/flotantes crudos según ``data.type``."""
    dtype = _DTYPES.get(props.get(f"channel.{channel}.data.type", "short"), ">i2")
    blob = zf.read(f"segments/{seg}/channels/{channel}.dat")
    return np.frombuffer(blob, dtype=dtype)


def _channel_value(
    raw: np.ndarray, channel: str, props: dict[str, str], stop_after: str | None = None
) -> np.ndarray:
    """Aplica encoder + conversiones de un canal hasta el slot ``stop_after``.

    ``stop_after="encoder"`` devuelve la salida del encoder (p. ej. voltios); ``None``
    aplica toda la cadena (unidad física final).
    """
    pfx = f"channel.{channel}"
    enc_m = float(props[f"{pfx}.data.encoder.scaling.multiplier"])
    enc_o = float(props[f"{pfx}.data.encoder.scaling.offset"])
    value = raw.astype(np.float64) * enc_m + enc_o
    if stop_after == "encoder":
        return value
    for slot in props.get(f"{pfx}.conversion-set.conversions.list", "").split():
        m = float(props[f"{pfx}.conversion-set.conversion.{slot}.scaling.multiplier"])
        o = float(props[f"{pfx}.conversion-set.conversion.{slot}.scaling.offset"])
        value = value * m + o
        if slot == stop_after:
            return value
    return value


def _slot_multiplier(channel: str, slot: str, props: dict[str, str]) -> float:
    return float(props[f"channel.{channel}.conversion-set.conversion.{slot}.scaling.multiplier"])


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
    """Lee un ``.jpk-force`` y devuelve un :class:`ForceCurve` calibrado."""
    path = Path(path)
    try:
        return _load_jpk_force(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Archivo .jpk-force no es un ZIP válido (¿corrupto?): {path}") from exc
    except KeyError as exc:
        raise ValueError(f"Archivo .jpk-force corrupto o incompleto (falta {exc}): {path}") from exc


def _load_jpk_force(path: Path) -> ForceCurve:
    with zipfile.ZipFile(path) as zf:
        seg_ids = sorted({int(m.group(1)) for name in zf.namelist() if (m := _SEG_RE.search(name))})
        if not seg_ids:
            raise ValueError(f"No es un .jpk-force válido (sin segmentos): {path}")

        segments: list[ForceSegment] = []
        invols: float | None = None
        spring_k: float | None = None

        for seg in seg_ids:
            props = _parse_properties(zf.read(f"segments/{seg}/segment-header.properties"))
            kind, direction = _segment_kind(props, seg)

            raw_h = _read_channel_raw(zf, seg, "height", props)
            raw_vd = _read_channel_raw(zf, seg, "vDeflection", props)
            height_m = _channel_value(raw_h, "height", props)
            volts = _channel_value(raw_vd, "vDeflection", props, stop_after="encoder")

            slots = props.get("channel.vDeflection.conversion-set.conversions.list", "").split()
            deflection = force = separation = None
            state: CalState = "raw_v"
            if "distance" in slots:
                deflection = _channel_value(raw_vd, "vDeflection", props, stop_after="distance")
                separation = height_m - deflection
                invols = _slot_multiplier("vDeflection", "distance", props)
                state = "deflection_m"
            if "force" in slots:
                force = _channel_value(raw_vd, "vDeflection", props, stop_after="force")
                spring_k = _slot_multiplier("vDeflection", "force", props)
                state = "force_n"

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
                    metadata={"num_points": int(raw_h.size)},
                )
            )

        calibration = None
        if invols is not None and spring_k is not None:
            calibration = Calibration(
                invols=invols,
                spring_constant=spring_k,
                method="jpk_metadata",
                provenance={"source": path.name},
            )

        return ForceCurve(
            segments=tuple(segments),
            calibration=calibration,
            metadata={"format": "jpk-force", "source_path": str(path)},
        )

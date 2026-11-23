"""Parser del formato NanoSurf ``.nid`` (clásico).

Estructura del archivo (verificada con archivos reales):

* Cabecera de texto tipo INI codificada en ``latin-1``.
* Un marcador binario ``#!`` (2 bytes) separa la cabecera de los datos.
* Tras el marcador van los bloques binarios de cada canal, en el orden en
  que se listan en la sección ``[DataSet]`` (grupos ``GrN-ChM``).
* Cada canal es ``Points x Lines`` muestras. El tipo se lee de la sección
  ``[DataSet-G:C]``: ``SaveBits`` (32), ``SaveSign`` (Signed),
  ``SaveOrder`` (Intel = little-endian).
* Conversión a unidades físicas (mapeo lineal del rango completo del entero
  con signo al rango ``[Dim2Min, Dim2Min + Dim2Range]``)::

      phys = Dim2Min + (raw + 2**(bits-1)) / 2**bits * Dim2Range
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from spmkit.core.models import (
    ForceCurve,
    ForceSegment,
    ForceVolume,
    SPMChannel,
    SPMData,
)

_MARKER = b"#!"
_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")


def _decode_header(raw: bytes) -> str:
    """Decodifica el header. NanoSurf usa UTF-8; latin-1 como respaldo."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse_ini(text: str) -> dict[str, dict[str, str]]:
    """Parsea el header INI a ``{seccion: {clave: valor}}``."""
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            current = {}
            sections[m.group("name")] = current
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        current[key.strip()] = value.strip()
    return sections


def _channel_order(dataset: dict[str, str]) -> list[str]:
    """Lista las secciones de canal en orden (``DataSet-G:C``)."""
    order: list[str] = []
    group_count = int(dataset.get("GroupCount", "0"))
    for g in range(group_count):
        prefix = f"Gr{g}-"
        ch_keys = sorted(
            (k for k in dataset if k.startswith(prefix) and "-Ch" in k),
            key=lambda k: int(k.split("-Ch")[1]),
        )
        for k in ch_keys:
            # valor tipo "DataSet-0:1" -> sección "DataSet-0:1"
            order.append(dataset[k])
    return order


def _dtype(section: dict[str, str]) -> np.dtype:
    bits = int(section.get("SaveBits", "32"))
    sign = section.get("SaveSign", "Signed").lower()
    byte_order = section.get("SaveOrder", "Intel").lower()
    mode = section.get("SaveMode", "Binary").lower()
    if mode != "binary":
        raise ValueError(f".nid: SaveMode no soportado: {mode!r}")
    if bits not in (8, 16, 32, 64):
        raise ValueError(f".nid: SaveBits no soportado: {bits}")
    if sign not in ("signed", "unsigned"):
        raise ValueError(f".nid: SaveSign no soportado: {sign!r}")
    if byte_order not in ("intel", "motorola"):
        raise ValueError(f".nid: SaveOrder no soportado: {byte_order!r}")
    order = "<" if byte_order == "intel" else ">"
    kind = "i" if sign == "signed" else "u"
    return np.dtype(f"{order}{kind}{bits // 8}")


def _to_physical(raw: np.ndarray, section: dict[str, str], bits: int, signed: bool) -> np.ndarray:
    dim2_min = float(section.get("Dim2Min", "0"))
    dim2_range = float(section.get("Dim2Range", "1"))
    raw_f = raw.astype(np.float64)
    if signed:  # noqa: SIM108 - if/else explícito documenta el mapeo físico
        # mapea [-2^(b-1), 2^(b-1)) → [0, 1)
        norm = (raw_f + 2 ** (bits - 1)) / 2**bits
    else:
        norm = raw_f / (2**bits - 1)
    return dim2_min + norm * dim2_range


def _direction(frame: str) -> str:
    return "backward" if "backward" in frame.lower() else "forward"


def _parse_cantilever_k(sections: dict[str, dict[str, str]]) -> float | None:
    """Extrae la constante de resorte del cantiléver (N/m) del header, si está.

    NanoSurf la guarda en ``[DataSet\\Calibration\\Cantilever]`` con formato tipado
    ``Prop0=D[2.66102]*[N/m]``.
    """
    cal = sections.get("DataSet\\Calibration\\Cantilever", {})
    for value in cal.values():
        m = re.search(r"D\[([\d.eE+\-]+)\]\s*\*\s*\[\s*N/m", value)
        if m:
            return float(m.group(1))
    return None


def load_nid(path: str | Path) -> SPMData:
    """Lee un archivo NanoSurf ``.nid`` y devuelve un :class:`SPMData`."""
    path = Path(path)
    blob = path.read_bytes()
    marker = blob.find(_MARKER)
    if marker == -1:
        raise ValueError(f"No es un .nid válido (sin marcador {_MARKER!r}): {path}")

    header_text = _decode_header(blob[:marker])
    bin_start = marker + len(_MARKER)
    sections = _parse_ini(header_text)

    if "DataSet" not in sections:
        raise ValueError(f"Header .nid sin sección [DataSet]: {path}")

    order = _channel_order(sections["DataSet"])
    channels: list[SPMChannel] = []
    offset = bin_start

    for sec_name in order:
        sec = sections.get(sec_name)
        if sec is None:
            raise ValueError(f".nid: falta la sección de canal {sec_name!r}")
        if "Points" not in sec or "Lines" not in sec:
            raise ValueError(
                f"Archivo .nid corrupto: el canal {sec_name!r} no declara Points/Lines: {path}"
            )
        points, lines = int(sec["Points"]), int(sec["Lines"])
        if points <= 0 or lines <= 0:
            raise ValueError(
                f"Archivo .nid corrupto: canal {sec_name!r} con dimensiones inválidas "
                f"({points}×{lines}): {path}"
            )
        dt = _dtype(sec)
        bits = int(sec.get("SaveBits", "32"))
        signed = sec.get("SaveSign", "Signed").lower() == "signed"
        count = points * lines
        need = count * dt.itemsize
        if offset + need > len(blob):
            raise ValueError(
                f"Archivo .nid truncado o corrupto: el canal {sec_name!r} necesita "
                f"{need} bytes pero solo quedan {len(blob) - offset}."
            )
        raw = np.frombuffer(blob, dtype=dt, count=count, offset=offset).reshape(lines, points)
        offset += need

        phys = _to_physical(raw, sec, bits, signed)
        # Solo las IMÁGENES se voltean verticalmente para coincidir con Gwyddion/NanoSurf
        # (validado: corr=1.0 con el .gwy del lab). Los canales de espectroscopía
        # (Dim1Name=SpecPoint) NO se voltean: sus filas son curvas independientes y
        # voltearlas reasignaría mal la posición espacial de cada curva.
        if sec.get("Dim1Name", "").startswith("Y"):
            phys = np.ascontiguousarray(np.flipud(phys))
        frame = sec.get("Frame", "")
        channels.append(
            SPMChannel(
                name=sec.get("Dim2Name", sec_name),
                data=phys,
                unit=sec.get("Dim2Unit", ""),
                x_range=float(sec.get("Dim0Range", "0")),
                y_range=float(sec.get("Dim1Range", "0")),
                direction=_direction(frame),
                group=frame,
                metadata=dict(sec),
            )
        )

    if not channels:
        raise ValueError(f"Archivo .nid sin canales legibles (¿corrupto o vacío?): {path}")

    metadata = {
        "format": "nid",
        "info": sections.get("DataSet-Info", {}),
        "version": sections["DataSet"].get("Version", ""),
        "spring_constant": _parse_cantilever_k(sections),  # N/m del cantiléver, si está
    }
    return SPMData(channels=tuple(channels), metadata=metadata, source_path=str(path))


# --------------------------------------------------------------------------- #
# Curvas de fuerza (espectroscopía) → ForceVolume
# --------------------------------------------------------------------------- #


def _find_channel(channels: list[SPMChannel], name: str, frame_contains: str) -> SPMChannel | None:
    """Canal inequívoco por nombre y frame."""
    matches = [
        c for c in channels if c.name == name and frame_contains in c.metadata.get("Frame", "")
    ]
    if len(matches) > 1:
        raise ValueError(f".nid: varios canales {name!r} coinciden con {frame_contains!r}")
    return matches[0] if matches else None


def load_nid_force(path: str | Path) -> ForceVolume:
    """Lee la espectroscopía de un ``.nid`` como :class:`ForceVolume`.

    NanoSurf guarda las curvas de fuerza como canales de espectroscopía
    (``Dim1Name=SpecPoint``): ``Deflection`` (N, ya calibrada) y ``Z-Axis Sensor``
    (m, altura) en ``Spec forward`` (extend) y ``Spec backward`` (retract). Si están,
    usa además los canales ``Tip-Sample Separation`` (m, separación ya computada por
    el instrumento; frames ``Indentation…Fwd/Bwd``). Cada fila es una curva.

    Devuelve un :class:`ForceVolume` de ``Lines`` curvas, cada una con segmentos
    extend/retract calibrados (``state="force_n"``).
    """
    data = load_nid(path)
    chs = list(data.channels)

    ext_force = _find_channel(chs, "Deflection", "Spec forward")
    ext_z = _find_channel(chs, "Z-Axis Sensor", "Spec forward")
    ret_force = _find_channel(chs, "Deflection", "Spec backward")
    ret_z = _find_channel(chs, "Z-Axis Sensor", "Spec backward")
    if ext_force is None or ext_z is None:
        raise ValueError(f"El .nid no contiene curvas de fuerza (canales Spec): {path}")

    ext_sep = _find_channel(chs, "Tip-Sample Separation", "Fwd")
    ret_sep = _find_channel(chs, "Tip-Sample Separation", "Bwd")

    def paired_force(separation: SPMChannel | None) -> SPMChannel | None:
        if separation is None or not separation.group.startswith("IndentationZSensor"):
            return None
        frame = separation.group.replace("IndentationZSensor", "IndentationDefl", 1)
        return next((c for c in chs if c.name == "Deflection" and c.group == frame), None)

    ext_sep_force = paired_force(ext_sep)
    ret_sep_force = paired_force(ret_sep)
    k = data.metadata.get("spring_constant")
    k = k if k is not None and math.isfinite(k) and k > 0 else None

    row_counts: dict[tuple[str, str], tuple[int, ...]] = {}
    for channel in (
        ext_force,
        ext_z,
        ret_force,
        ret_z,
        ext_sep,
        ret_sep,
        ext_sep_force,
        ret_sep_force,
    ):
        if channel is None:
            continue
        row_counts[channel.group, channel.name] = channel.spectroscopy_point_counts()
        try:
            offset = float(channel.metadata["Dim2Min"])
            span = float(channel.metadata["Dim2Range"])
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"{channel.group} / {channel.name}: falta escala física válida"
            ) from exc
        if not math.isfinite(offset) or not math.isfinite(span) or span <= 0:
            raise ValueError(f"{channel.group} / {channel.name}: escala física inválida")

    n_curves = int(ext_force.data.shape[0])

    if (ret_force is None) != (ret_z is None):
        raise ValueError("Retracción .nid incompleta: se requieren Deflection y Z-Axis Sensor")

    def in_si_row(channel: SPMChannel, unit: str, i: int) -> np.ndarray:
        prefix_scale = {"": 1.0, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
        declared = channel.unit.strip().replace("µ", "u").replace("μ", "u")
        prefix = declared.removesuffix(unit)
        if not declared.endswith(unit) or prefix not in prefix_scale:
            raise ValueError(f"{channel.name}: unidad {channel.unit!r} incompatible con {unit}")
        if channel.data.shape[0] != n_curves:
            raise ValueError(f"{channel.name}: número de curvas incompatible")
        points = row_counts[channel.group, channel.name][i]
        row = np.asarray(channel.data[i, :points], dtype=np.float64)
        return row if prefix_scale[prefix] == 1.0 else row * prefix_scale[prefix]

    def _segment(
        kind: str,
        direction: str,
        z_ch: SPMChannel,
        f_ch: SPMChannel,
        sep_ch: SPMChannel | None,
        sep_force_ch: SPMChannel | None,
        i: int,
    ) -> ForceSegment:
        height = in_si_row(z_ch, "m", i)
        force = in_si_row(f_ch, "N", i)
        separation = in_si_row(sep_ch, "m", i) if sep_ch is not None else None
        if height.shape != force.shape:
            raise ValueError(f"{kind}: longitudes de canal incompatibles")
        separation_status = "absent"
        if separation is not None:
            separation_status = "unverified"
            if separation.shape != height.shape:
                separation = None
                separation_status = "length_mismatch"
            elif sep_force_ch is not None:
                paired_force = in_si_row(sep_force_ch, "N", i)
                if np.array_equal(force, paired_force):
                    separation_status = "matched"
                else:
                    separation = None
                    separation_status = "force_mismatch"
        deflection = force / k if k is not None else None
        return ForceSegment(
            segment_type=kind,  # type: ignore[arg-type]
            direction=direction,
            raw_height=height,
            raw_deflection=force,
            deflection=deflection,
            force=force,
            separation=separation,
            state="force_n",
            metadata={
                "num_points": int(height.size),
                "stored_force_points": f_ch.shape[1],
                "height_channel": z_ch.name,
                "height_input_unit": z_ch.unit,
                "raw_deflection_unit": "N",
                "force_input_unit": f_ch.unit,
                "force_channel": f_ch.name,
                "force_frame": f_ch.group,
                "separation_status": separation_status,
                "spring_constant_n_per_m": k,
            },
        )

    def _load_curve(i: int) -> ForceCurve:
        segments = [_segment("extend", "approach", ext_z, ext_force, ext_sep, ext_sep_force, i)]
        if ret_force is not None and ret_z is not None:
            segments.append(
                _segment("retract", "retract", ret_z, ret_force, ret_sep, ret_sep_force, i)
            )
        return ForceCurve(segments=tuple(segments), index=i, metadata={"format": "nid"})

    curves = tuple(_load_curve(i) for i in range(n_curves))

    # Grilla espacial: cuadrada si es un cuadrado perfecto, si no una línea 1×N.
    side = int(math.isqrt(n_curves))
    grid_shape = (side, side) if side * side == n_curves else (1, n_curves)
    # Extensión XY del mapa: del canal de topografía si existe, si no desconocida.
    topo = _find_channel(chs, "Z-Axis", "Scan forward")
    x_range = float(topo.x_range) if topo is not None else 0.0
    y_range = float(topo.y_range) if topo is not None else 0.0

    return ForceVolume.from_curves(
        curves,
        grid_shape=grid_shape,
        x_range=x_range,
        y_range=y_range,
        metadata={
            "format": "nid",
            "source_path": str(path),
            "spring_constant": k,
        },
    )

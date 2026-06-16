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

import re
from pathlib import Path

import numpy as np

from spmkit.core.models import SPMChannel, SPMData

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
    order = "<" if section.get("SaveOrder", "Intel").lower() == "intel" else ">"
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
            continue
        points = int(sec["Points"])
        lines = int(sec["Lines"])
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

    metadata = {
        "format": "nid",
        "info": sections.get("DataSet-Info", {}),
        "version": sections["DataSet"].get("Version", ""),
    }
    return SPMData(channels=tuple(channels), metadata=metadata, source_path=str(path))

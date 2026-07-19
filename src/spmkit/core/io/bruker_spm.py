"""Lector **EXPERIMENTAL** del formato Bruker / Nanoscope ``.spm`` (imagen AFM).

.. warning::

    **Experimental y sin validar contra archivos reales.** Reimplementado desde la
    especificación pública del formato Nanoscope, tomando como **referencia** (sin usar su
    código) la librería `AFMReader <https://github.com/AFM-SPM/AFMReader>`_ (GPL-3.0) y
    `TopoStats <https://github.com/AFM-SPM/TopoStats>`_ (DOI 10.15131/shef.data.22633528),
    del grupo AFM-SPM. La **cadena de escalado** de Nanoscope (``hard scale`` × sensibilidad
    ``soft``) depende de la versión del instrumento; esta implementación cubre el caso común
    (Nanoscope III/V, enteros de 2/4 bytes) y **debe validarse contra un ``.spm`` real** antes
    de confiar en los valores físicos absolutos. Si no puede resolver el escalado, devuelve el
    **crudo** (``metadata["scaled"] = False``) en vez de inventar una calibración.

Estructura del archivo:

* Cabecera de **texto** (latin-1) de líneas ``\\Clave: valor`` agrupadas en secciones
  ``\\*Nombre``; empieza en ``\\*File list`` y termina en ``\\*File list end``.
* Tras la cabecera van los **bloques binarios** de cada canal, en el byte que indica su
  ``\\Data offset`` (enteros con signo, little-endian, ``Bytes/pixel`` por muestra).
* Conversión física (por LSB): ``z = crudo · hard[unidad/LSB] · sens[física/unidad]``.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np

from spmkit.core.models import SPMChannel, SPMData

#: Marca de "no validado": la GUI/CLI puede advertir antes de confiar en los valores.
EXPERIMENTAL = True

_MAGIC = b"\\*File list"
_SECTION_RE = re.compile(rb"^\\\*(?P<name>.+?)\s*$")
# Nanoscope: la clave puede llevar colon en el prefijo ``@N:`` (p. ej. ``@2:Z scale``);
# el separador clave/valor es un colon **seguido de espacio**.
_KEY_RE = re.compile(rb"^\\(?P<key>@?.+?):\s(?P<val>.*?)\s*$")
#: ``\@2:Z scale: V [Sens. Zscale] (0.00615 nm/LSB)`` → (sens_ref, hard, unidad).
_ZSCALE_RE = re.compile(
    r"\[(?P<ref>[^\]]+)\]\s*\(?\s*(?P<hard>[-\d.eE+]+)\s*(?P<unit>\S+)\)"
    r"(?:\s*(?P<value>[-\d.eE+]+)\s*(?P<value_unit>\S+))?"
)
#: ``\@Sens. Zscale: V 34.5 nm/V`` → (valor, unidad).
_SENS_RE = re.compile(r"([-\d.eE+]+)\s*(\S+)")
_UNIT_TO_M = {"m": 1.0, "mm": 1e-3, "um": 1e-6, "µm": 1e-6, "~m": 1e-6, "nm": 1e-9, "pm": 1e-12}


def looks_like_bruker_spm(path: str | Path) -> bool:
    """``True`` si ``path`` empieza con la magia de Nanoscope (reconoce ``.spm`` y ``.00N``)."""
    try:
        with open(path, "rb") as fh:  # noqa: PTH123 - solo los primeros bytes
            return fh.read(len(_MAGIC)) == _MAGIC
    except OSError:
        return False


def _parse_header(blob: bytes) -> list[tuple[str, dict[str, str]]]:
    """Cabecera de texto → lista ``[(sección, {clave: valor})]`` (orden preservado)."""
    end = blob.find(b"\\*File list end")
    if end == -1:
        end = blob.find(b"\x1a")  # algunos .spm terminan con 0x1A (EOF de DOS)
    header = blob[:end] if end != -1 else blob[:1_000_000]
    sections: list[tuple[str, dict[str, str]]] = []
    current: dict[str, str] | None = None
    for raw in header.splitlines():
        m = _SECTION_RE.match(raw)
        if m:
            current = {}
            sections.append((m.group("name").decode("latin-1"), current))
            continue
        if current is None:
            continue
        km = _KEY_RE.match(raw)
        if km:
            current[km.group("key").decode("latin-1")] = km.group("val").decode("latin-1")
    return sections


def _scan_size(sections: list[tuple[str, dict[str, str]]]) -> tuple[float, float]:
    """Extensión (X, Y) del escaneo en metros (de ``\\Scan Size``), o ``(0, 0)`` si no está.

    Nanoscope da ``Scan Size: X Y unit`` (o ``X unit`` si es cuadrado). Se leen **ambas**
    dimensiones: un escaneo no cuadrado tiene X ≠ Y.
    """
    for _name, keys in sections:
        raw = keys.get("Scan Size") or keys.get("Scan size")
        if not raw:
            continue
        parts = raw.split()
        nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw)]
        factor = _UNIT_TO_M.get(parts[-1], 1.0) if parts else 1.0
        if len(nums) >= 2:
            return nums[0] * factor, nums[1] * factor  # X, Y (puede ser no cuadrado)
        if nums:
            return nums[0] * factor, nums[0] * factor
    return 0.0, 0.0


def _sensitivity(sections: list[tuple[str, dict[str, str]]], ref: str) -> float | None:
    key = f"@Sens. {ref.removeprefix('Sens. ')}"
    for _name, keys in sections:
        for k, v in keys.items():
            if k == key:
                m = _SENS_RE.search(v)
                if m:
                    unit = m.group(2).split("/", 1)[0]
                    factor = _UNIT_TO_M.get(unit)
                    if factor is not None:
                        return float(m.group(1)) * factor
    return None


def _int_dtype(bytes_per_pixel: int) -> np.dtype:
    if bytes_per_pixel == 2:
        return np.dtype("<i2")
    if bytes_per_pixel == 4:
        return np.dtype("<i4")
    raise ValueError(f"Variante .spm no soportada: {bytes_per_pixel} bytes/pixel")


def _pixel_layout(sections: list[tuple[str, dict[str, str]]], keys: dict[str, str]) -> tuple[np.dtype, int]:
    declared = int(keys.get("Bytes/pixel", "2"))
    _int_dtype(declared)
    version = 0
    for name, values in sections:
        if name == "File list" and values.get("Version"):
            version = int(values["Version"], 0)
            break
    return _int_dtype(4 if version >= 0x09200000 else 2), declared


def load_bruker_spm(path: str | Path) -> SPMData:
    """Lee un ``.spm`` de Bruker/Nanoscope como :class:`SPMData` (**experimental**)."""
    warnings.warn(
        "Lector Bruker .spm EXPERIMENTAL: escalado sin validar contra archivos reales.",
        stacklevel=2,
    )
    path = Path(path)
    blob = path.read_bytes()
    if not blob.startswith(_MAGIC):
        raise ValueError(f"No es un .spm de Nanoscope (sin magia {_MAGIC!r}): {path}")

    sections = _parse_header(blob)
    x_range, y_range = _scan_size(sections)
    channels: list[SPMChannel] = []
    scaled_any = False

    for name, keys in sections:
        if "image" not in name.lower() or "Data offset" not in keys:
            continue
        try:
            offset = int(keys["Data offset"])
            samps = int(keys.get("Samps/line") or keys["Number of Samps/line"])
            lines = int(keys["Number of lines"])
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f".spm corrupto: sección {name!r} sin dimensiones ({exc}): {path}"
            ) from exc

        try:
            dt, qbpp = _pixel_layout(sections, keys)
        except ValueError as exc:
            raise ValueError(f"{exc}: {path}") from exc
        count = samps * lines
        need = count * dt.itemsize
        if offset + need > len(blob):
            raise ValueError(f".spm truncado: el canal {name!r} excede el archivo: {path}")
        raw = np.frombuffer(blob, dtype=dt, count=count, offset=offset).reshape(lines, samps)

        # Nombre del canal y escalado (hard × sens). Sin escala confiable → crudo.
        label = _by_suffix(keys, "Image Data") or name
        cname = _channel_name(label)
        scale, unit = _channel_scale(keys, sections, qbpp)
        data = raw.astype(np.float64) * scale
        if scale != 1.0:
            scaled_any = True
        channels.append(
            SPMChannel(
                name=cname,
                data=np.ascontiguousarray(np.flipud(data)),  # Nanoscope: fila 0 = arriba
                unit=unit,
                x_range=x_range,
                y_range=y_range,
                direction="forward",
                metadata=dict(keys),
            )
        )

    if not channels:
        raise ValueError(f".spm sin canales de imagen legibles (¿corrupto?): {path}")
    return SPMData(
        channels=tuple(channels),
        metadata={"format": "bruker-spm", "experimental": True, "scaled": scaled_any},
        source_path=str(path),
    )


def _by_suffix(keys: dict[str, str], suffix: str) -> str | None:
    """Valor de la primera clave que termina en ``suffix`` (prefijo ``@N:`` variable)."""
    return next((v for k, v in keys.items() if k.endswith(suffix)), None)


def _channel_name(label: str) -> str:
    """Nombre legible del canal de ``\\@N:Image Data: S [Height] "Height"``."""
    m = re.search(r'"([^"]+)"', label) or re.search(r"\[([^\]]+)\]", label)
    return m.group(1) if m else label.strip() or "Data"


def _channel_scale(
    keys: dict[str, str], sections: list[tuple[str, dict[str, str]]], qbpp: int
) -> tuple[float, str]:
    """``(factor, unidad)`` para convertir el crudo a físico. ``(1.0, "")`` si no se resuelve."""
    zscale = _by_suffix(keys, "Z scale")
    if not zscale:
        return 1.0, ""
    m = _ZSCALE_RE.search(zscale)
    if not m:
        return 1.0, ""
    hard = float(m.group("hard"))
    hard_unit = m.group("unit").split("/")[0]
    sens = _sensitivity(sections, m.group("ref"))
    hard_factor = _UNIT_TO_M.get(hard_unit)
    if hard_factor is not None:
        return hard * hard_factor, "m"
    value = m.group("value")
    value_unit = (m.group("value_unit") or "").split("/", 1)[0]
    if value is not None and value_unit in {"V", "mV"} and sens is not None:
        volts_per_lsb = float(value) * (1e-3 if value_unit == "mV" else 1.0)
        return volts_per_lsb * sens / 256**qbpp, "m"
    if hard_unit in {"V", "mV"} and sens is not None:
        volts_per_lsb = hard * (1e-3 if hard_unit == "mV" else 1.0)
        return volts_per_lsb * sens, "m"
    return 1.0, ""

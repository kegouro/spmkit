"""Limited native reader for observed Igor Binary Wave v5 AFM image files.

This reader intentionally supports only the structural family exercised by the
native-IBW pilot: little-endian v5 headers, scalar FP32 samples, and 2D image
channels stored in the third dimension.  It does not claim general ``.ibw``
support and leaves unsupported variants available to optional readers.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np

from spmkit.core.models import SPMChannel, SPMData
from spmkit.core.plugins.contracts import DatasetInfo

_BIN_HEADER_SIZE: Final = 64
_WAVE_HEADER_SIZE: Final = 320
_HEADER_SIZE: Final = _BIN_HEADER_SIZE + _WAVE_HEADER_SIZE
_IGOR_V5: Final = 5
_IGOR_SINGLE: Final = 0x02
_LABEL_SIZE: Final = 32
_UNIT_TO_METERS: Final = {
    "m": 1.0,
    "mm": 1e-3,
    "um": 1e-6,
    "µm": 1e-6,
    "nm": 1e-9,
    "pm": 1e-12,
}
_TITLE_UNITS: Final = (
    ("Height", "m"),
    ("ZSensor", "m"),
    ("Deflection", "m"),
    ("Amplitude", "m"),
    ("Phase", "deg"),
    ("Current", "A"),
    ("Frequency", "Hz"),
    ("Capacitance", "F"),
    ("Potential", "V"),
)


class IbwFormatError(ValueError):
    """Malformed or unsupported Igor Binary Wave data."""


@dataclass(frozen=True)
class _Header:
    dimensions: tuple[int, int, int, int]
    scales: tuple[float, float, float, float]
    data_unit: str
    dimension_units: tuple[str, str, str, str]
    data_end: int
    extra_start: int
    formula_size: int
    note_size: int
    data_e_units_size: int
    dimension_e_units_sizes: tuple[int, int, int, int]
    dimension_label_sizes: tuple[int, int, int, int]


def _read_c_string(value: bytes) -> str:
    return value.split(b"\0", 1)[0].decode("latin-1", "replace").strip()


def _span(blob: bytes, start: int, size: int, label: str) -> bytes:
    end = start + size
    if start < 0 or size < 0 or end > len(blob):
        raise IbwFormatError(f"IBW v5 truncated: {label} exceeds file size")
    return blob[start:end]


def _checksum_ok(header: bytes) -> bool:
    if len(header) != _HEADER_SIZE:
        return False
    words = struct.unpack(f"<{len(header) // 2}H", header)
    return sum(words) & 0xFFFF == 0


def _parse_header(blob: bytes, *, validate_payload: bool = True) -> _Header:
    if len(blob) < _HEADER_SIZE:
        raise IbwFormatError("IBW v5 truncated before the binary headers")
    if blob[0] == 0:
        raise IbwFormatError("IBW big-endian files are not supported by this native reader")
    version = struct.unpack_from("<H", blob, 0)[0]
    if version != _IGOR_V5:
        raise IbwFormatError(f"IBW version {version} is not supported; expected v5")
    if not _checksum_ok(blob[:_HEADER_SIZE]):
        raise IbwFormatError("IBW v5 header checksum is invalid")

    wfm_size = struct.unpack_from("<I", blob, 4)[0]
    formula_size, note_size, data_e_units_size = struct.unpack_from("<III", blob, 8)
    dim_e0, dim_e1, dim_e2, dim_e3 = struct.unpack_from("<4I", blob, 20)
    dim_l0, dim_l1, dim_l2, dim_l3 = struct.unpack_from("<4I", blob, 36)
    npts = struct.unpack_from("<I", blob, 76)[0]
    sample_type = struct.unpack_from("<H", blob, 80)[0]
    if sample_type != _IGOR_SINGLE:
        raise IbwFormatError(
            f"IBW sample type 0x{sample_type:04x} is not supported; expected scalar FP32"
        )

    xres, yres, channels, fourth_dimension = struct.unpack_from("<4I", blob, 132)
    dimensions = (xres, yres, channels, fourth_dimension)
    if fourth_dimension:
        raise IbwFormatError("IBW four-dimensional data are not supported")
    if not xres or not yres or not channels:
        raise IbwFormatError("IBW v5 reader requires non-empty 2D image channels")
    expected_points = xres * yres * channels
    if npts != expected_points:
        raise IbwFormatError("IBW point count does not match its declared 2D channel dimensions")
    expected_wfm_size = _WAVE_HEADER_SIZE + npts * np.dtype("<f4").itemsize
    if wfm_size != expected_wfm_size:
        raise IbwFormatError("IBW waveform size does not match scalar FP32 image payload")

    data_end = _BIN_HEADER_SIZE + wfm_size
    if validate_payload:
        _span(blob, _HEADER_SIZE, npts * np.dtype("<f4").itemsize, "image payload")
    scale_x, scale_y, scale_z, scale_fourth = struct.unpack_from("<4d", blob, 148)
    scales = (scale_x, scale_y, scale_z, scale_fourth)
    if not np.isfinite(scales[:2]).all() or scales[0] <= 0 or scales[1] <= 0:
        raise IbwFormatError("IBW lateral scale is invalid")
    return _Header(
        dimensions=dimensions,
        scales=scales,
        data_unit=_read_c_string(blob[212:216]),
        dimension_units=(
            _read_c_string(blob[216:220]),
            _read_c_string(blob[220:224]),
            _read_c_string(blob[224:228]),
            _read_c_string(blob[228:232]),
        ),
        data_end=data_end,
        extra_start=data_end,
        formula_size=formula_size,
        note_size=note_size,
        data_e_units_size=data_e_units_size,
        dimension_e_units_sizes=(dim_e0, dim_e1, dim_e2, dim_e3),
        dimension_label_sizes=(dim_l0, dim_l1, dim_l2, dim_l3),
    )


def _label_sections(blob: bytes, header: _Header) -> tuple[list[str], dict[str, str]]:
    position = header.extra_start
    position += header.formula_size
    note_bytes = _span(blob, position, header.note_size, "note")
    position += header.note_size + header.data_e_units_size + sum(header.dimension_e_units_sizes)
    for size in header.dimension_label_sizes[:2]:
        _span(blob, position, size, "lower-dimension labels")
        position += size
    channel_size = header.dimension_label_sizes[2]
    channel_blob = _span(blob, position, channel_size, "channel labels")
    if channel_size % _LABEL_SIZE:
        raise IbwFormatError("IBW channel-label block is not aligned to the v5 label size")
    labels = [
        _read_c_string(channel_blob[i : i + _LABEL_SIZE])
        for i in range(0, channel_size, _LABEL_SIZE)
    ]
    _span(blob, position + channel_size, sum(header.dimension_label_sizes[3:]), "trailing labels")
    _, _, channels, _ = header.dimensions
    if len(labels) < channels + 1:
        raise IbwFormatError("IBW channel-label block is shorter than the declared channel count")
    parsed_note: dict[str, str] = {}
    for raw in note_bytes.decode("latin-1", "replace").replace("\r", "\n").split("\n"):
        if ":" in raw:
            key, value = raw.split(":", 1)
            parsed_note[key.strip()] = value.strip()
    return labels[1 : channels + 1], parsed_note


def _canonical_name(label: str) -> str:
    name = label or "Unknown"
    marker = name.find("Mod")
    if marker != -1 and name[marker + 3 :].isdigit():
        name = name[:marker]
    for suffix in ("Retrace", "Trace"):
        if name.endswith(suffix):
            return name[: -len(suffix)] or "Unknown"
    return name


def _direction(label: str) -> str:
    return "backward" if label.endswith("Retrace") else "forward"


def _channel_unit(label: str, header_unit: str, note: dict[str, str]) -> tuple[str, float]:
    name = _canonical_name(label)
    note_unit = note.get(f"{name}Unit", "")
    unit = note_unit or header_unit
    for prefix, known_unit in _TITLE_UNITS:
        if name.startswith(prefix):
            unit = known_unit
            break
    scale = _UNIT_TO_METERS.get(unit, 1.0)
    return unit or "", scale


def _lateral_range(scale: float, unit: str, resolution: int) -> float:
    factor = _UNIT_TO_METERS.get(unit)
    if factor is None:
        raise IbwFormatError(f"IBW lateral unit {unit!r} is not supported")
    return scale * resolution * factor


def _inspect_limited_header(source: Path) -> tuple[_Header, list[str]]:
    with open(source, "rb") as file:  # noqa: PTH123 - header and metadata only
        header_blob = file.read(_HEADER_SIZE)
        header = _parse_header(header_blob, validate_payload=False)
        file.seek(0, 2)
        if file.tell() < header.data_end:
            raise IbwFormatError("IBW v5 truncated: image payload exceeds file size")
        file.seek(header.extra_start)
        extra_size = (
            header.formula_size
            + header.note_size
            + header.data_e_units_size
            + sum(header.dimension_e_units_sizes)
            + sum(header.dimension_label_sizes)
        )
        extras = file.read(extra_size)
    labels, _note = _label_sections(
        header_blob + b"\0" * (header.extra_start - _HEADER_SIZE) + extras, header
    )
    return header, labels


def looks_like_limited_igor_ibw(path: str | Path) -> bool:
    try:
        _inspect_limited_header(Path(path))
        return True
    except (IbwFormatError, OSError):
        return False


def inspect_igor_ibw(path: str | Path) -> DatasetInfo:
    source = Path(path)
    header, labels = _inspect_limited_header(source)
    return DatasetInfo(
        path=source,
        format="igor-ibw-v5-native-limited",
        kinds=("image",),
        channels=tuple(_canonical_name(label) for label in labels),
        metadata={
            "ibw_version": _IGOR_V5,
            "endianness": "little",
            "sample_type": "fp32",
            "declared_shape": header.dimensions,
        },
    )


def load_igor_ibw(path: str | Path) -> SPMData:
    source = Path(path)
    blob = source.read_bytes()
    header = _parse_header(blob)
    labels, note = _label_sections(blob, header)
    xres, yres, channels, _ = header.dimensions
    samples = np.frombuffer(blob, dtype="<f4", count=xres * yres * channels, offset=_HEADER_SIZE)
    raw_channels = samples.reshape(channels, yres, xres)
    x_range = _lateral_range(header.scales[0], header.dimension_units[0], xres)
    y_range = _lateral_range(header.scales[1], header.dimension_units[1], yres)
    loaded_channels: list[SPMChannel] = []
    for index, label in enumerate(labels):
        unit, unit_scale = _channel_unit(label, header.data_unit, note)
        data = np.ascontiguousarray(np.flipud(raw_channels[index].astype(np.float64) * unit_scale))
        loaded_channels.append(
            SPMChannel(
                name=_canonical_name(label),
                data=data,
                unit=unit,
                x_range=x_range,
                y_range=y_range,
                direction=_direction(label),
                metadata={
                    "format": "igor-ibw-v5-native-limited",
                    "source_label": label,
                    "ibw_version": _IGOR_V5,
                    "endianness": "little",
                    "sample_type": "fp32",
                },
            )
        )
    return SPMData(
        channels=tuple(loaded_channels),
        metadata={
            "format": "igor-ibw-v5-native-limited",
            "limited": True,
            "ibw_version": _IGOR_V5,
            "endianness": "little",
            "sample_type": "fp32",
            "declared_shape": header.dimensions,
        },
        source_path=str(source),
    )

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io import inspect_any, load_any
from spmkit.core.io.igor_ibw import IbwFormatError, load_igor_ibw, looks_like_limited_igor_ibw
from spmkit.core.io.readers import IgorIbwReader
from spmkit.core.plugins import registry


def _checksum(header: bytearray) -> None:
    struct.pack_into("<H", header, 2, 0)
    checksum = (-sum(struct.unpack(f"<{384 // 2}H", header[:384]))) & 0xFFFF
    struct.pack_into("<H", header, 2, checksum)


def _labels(values: list[str]) -> bytes:
    return b"".join(value.encode("latin-1")[:31].ljust(32, b"\0") for value in values)


def _write_ibw(
    path: Path,
    data: np.ndarray,
    *,
    labels: list[str] | None = None,
    dimensions: tuple[int, int, int, int] | None = None,
    sample_type: int = 0x02,
    scale: tuple[float, float] = (2e-9, 3e-9),
    dimension_unit: str = "m",
    data_unit: str = "m",
    wfm_size: int | None = None,
) -> None:
    channels, yres, xres = data.shape
    dimensions = dimensions or (xres, yres, channels, 0)
    declared_points = dimensions[0] * dimensions[1] * dimensions[2]
    payload = data.astype("<f4", copy=False).tobytes()
    labels = labels or ["", "HeightTrace", "PhaseRetrace"][: channels + 1]
    label_blob = _labels(labels)
    header = bytearray(384)
    struct.pack_into("<H", header, 0, 5)
    struct.pack_into("<I", header, 4, wfm_size or 320 + len(payload))
    struct.pack_into("<4I", header, 36, 0, 0, len(label_blob), 0)
    struct.pack_into("<I", header, 76, declared_points)
    struct.pack_into("<H", header, 80, sample_type)
    struct.pack_into("<4I", header, 132, *dimensions)
    struct.pack_into("<4d", header, 148, scale[0], scale[1], 1.0, 1.0)
    header[212:216] = data_unit.encode("latin-1")[:3].ljust(4, b"\0")
    for index in range(2):
        start = 216 + 4 * index
        header[start : start + 4] = dimension_unit.encode("latin-1")[:3].ljust(4, b"\0")
    _checksum(header)
    path.write_bytes(header + payload + label_blob)


def test_load_limited_ibw_v5_channels_scaling_shape_and_orientation(tmp_path: Path) -> None:
    raw = np.array(
        [
            [[1e-9, 2e-9, 3e-9], [4e-9, 5e-9, 6e-9]],
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        ],
        dtype=np.float32,
    )
    path = tmp_path / "image.ibw"
    _write_ibw(path, raw)

    loaded = load_igor_ibw(path)

    assert loaded.names == ["Height", "Phase"]
    height, phase = loaded.channels
    assert height.shape == (2, 3)
    assert height.x_range == pytest.approx(6e-9)
    assert height.y_range == pytest.approx(6e-9)
    assert height.unit == "m" and phase.unit == "deg"
    assert height.direction == "forward" and phase.direction == "backward"
    assert np.array_equal(height.data, np.flipud(raw[0]).astype(np.float64))
    assert np.array_equal(phase.data, np.flipud(raw[1]).astype(np.float64))
    assert loaded.metadata["format"] == "igor-ibw-v5-native-limited"


def test_inspect_and_public_dispatch_use_native_reader(tmp_path: Path) -> None:
    path = tmp_path / "native.ibw"
    _write_ibw(path, np.zeros((2, 2, 2), dtype=np.float32))

    assert looks_like_limited_igor_ibw(path)
    info = inspect_any(path)
    loaded, kind = load_any(path)

    assert info.format == "igor-ibw-v5-native-limited"
    assert info.channels == ("Height", "Phase")
    assert kind == "image" and loaded.names == ["Height", "Phase"]


@pytest.mark.parametrize(
    ("shape", "labels"),
    [
        (
            (4, 256, 256),
            ["", "HeightRetrace", "AmplitudeRetrace", "PhaseRetrace", "ZSensorRetrace"],
        ),
        ((3, 1024, 1024), ["", "HeightRetrace", "DeflectionRetrace", "ZSensorRetrace"]),
    ],
)
def test_loads_each_frozen_structural_shape(
    tmp_path: Path, shape: tuple[int, int, int], labels: list[str]
) -> None:
    path = tmp_path / "frozen-shape.ibw"
    _write_ibw(path, np.zeros(shape, dtype=np.float32), labels=labels)

    loaded = load_igor_ibw(path)

    assert len(loaded.channels) == shape[0]
    assert all(channel.shape == shape[1:] for channel in loaded.channels)
    assert all(channel.direction == "backward" for channel in loaded.channels)


def test_unsupported_native_header_can_reach_a_later_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FallbackReader:
        extensions = (".ibw",)

        def inspect(self, path: str | Path) -> object:
            return path

        def load(self, path: str | Path, kind: object = None) -> object:
            return path

    path = tmp_path / "unsupported.ibw"
    path.write_bytes(b"\x04\0" + b"\0" * 382)
    fallback = FallbackReader()
    monkeypatch.setattr(registry, "_READERS", [IgorIbwReader(), fallback])
    monkeypatch.setattr(registry, "_discovered", True)

    assert registry.reader_for(path) is fallback


def test_non_ibw_content_is_not_detected(tmp_path: Path) -> None:
    path = tmp_path / "not-an-ibw.ibw"
    path.write_bytes(b"not an igor binary wave")

    assert not looks_like_limited_igor_ibw(path)


@pytest.mark.parametrize(
    ("mutator", "message", "rechecksum"),
    [
        (lambda value: value.__setitem__(slice(0, 2), b"\0\x05"), "big-endian", True),
        (lambda value: value.__setitem__(2, value[2] ^ 1), "checksum", False),
        (lambda value: struct.pack_into("<H", value, 80, 0x04), "sample type", True),
        (lambda value: struct.pack_into("<I", value, 4, 321), "waveform size", True),
        (lambda value: struct.pack_into("<I", value, 144, 1), "four-dimensional", True),
    ],
)
def test_rejects_unsupported_or_malformed_header(
    tmp_path: Path, mutator, message: str, rechecksum: bool
) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "bad.ibw"
    _write_ibw(path, np.zeros((1, 2, 2), dtype=np.float32), labels=["", "HeightTrace"])
    raw = bytearray(path.read_bytes())
    mutator(raw)
    if rechecksum:
        _checksum(raw)
    path.write_bytes(raw)

    with pytest.raises(IbwFormatError, match=message):
        load_igor_ibw(path)


def test_rejects_truncated_header_payload_and_channel_labels(tmp_path: Path) -> None:
    header = tmp_path / "header.ibw"
    header.write_bytes(b"\x05\0")
    with pytest.raises(IbwFormatError, match="truncated"):
        load_igor_ibw(header)

    payload = tmp_path / "payload.ibw"
    _write_ibw(payload, np.zeros((1, 2, 2), dtype=np.float32), labels=["", "HeightTrace"])
    payload.write_bytes(payload.read_bytes()[:399])
    with pytest.raises(IbwFormatError, match="payload"):
        load_igor_ibw(payload)

    labels = tmp_path / "labels.ibw"
    _write_ibw(labels, np.zeros((2, 2, 2), dtype=np.float32), labels=["", "HeightTrace"])
    with pytest.raises(IbwFormatError, match="shorter"):
        load_igor_ibw(labels)


def test_native_reader_does_not_import_gui_or_optional_parsers(tmp_path: Path) -> None:
    path = tmp_path / "nogui.ibw"
    _write_ibw(path, np.zeros((1, 2, 2), dtype=np.float32), labels=["", "HeightTrace"])
    before = set(sys.modules)

    load_igor_ibw(path)

    imported = set(sys.modules) - before
    assert not any(name.startswith(("PyQt", "pyqtgraph", "afmformats")) for name in imported)

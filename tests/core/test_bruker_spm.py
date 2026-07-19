"""Lector EXPERIMENTAL Bruker/Nanoscope .spm: parseo + escalado (validación sintética).

Verifica la lógica de parseo y la conversión crudo→físico que implementa el lector, con un
``.spm`` mínimo construido con escala conocida. La fidelidad contra archivos Bruker reales
queda pendiente (el escalado de Nanoscope depende de versión; ver el docstring del módulo).
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

from spmkit.core.io.bruker_spm import load_bruker_spm, looks_like_bruker_spm


def _write_spm(
    path, raw: np.ndarray, hard: float, sens: float, scan_um: float, scan_y_um: float | None = None
) -> None:
    """Escribe un .spm Nanoscope mínimo: 1 canal Height int16 con escala (hard·sens)."""
    lines, samps = raw.shape
    scan_y = scan_um if scan_y_um is None else scan_y_um
    # offset con ancho fijo (10 dígitos) → su longitud no cambia al rellenar el valor real.
    template = (
        "\\*File list\r\n"
        "\\*Ciao scan list\r\n"
        f"\\Scan Size: {scan_um} {scan_y} ~m\r\n"
        f"\\@Sens. Zscale: V {sens} nm/V\r\n"
        "\\*Ciao image list\r\n"
        "\\Data offset: {off:010d}\r\n"
        f"\\Data length: {raw.size * 2}\r\n"
        "\\Bytes/pixel: 2\r\n"
        f"\\Samps/line: {samps}\r\n"
        f"\\Number of lines: {lines}\r\n"
        '\\@2:Image Data: S [Height] "Height"\r\n'
        f"\\@2:Z scale: V [Zscale] ({hard} V/LSB)\r\n"
        "\\*File list end\r\n"
    )
    offset = len(template.format(off=0).encode("latin-1"))
    header = template.format(off=offset).encode("latin-1")
    path.write_bytes(header + raw.astype("<i2").tobytes())


def test_bruker_spm_parse_y_escala(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = np.arange(16, dtype=np.int16).reshape(4, 4)
    hard, sens, scan_um = 2.0, 3.0, 5.0
    p = tmp_path / "scan.spm"
    _write_spm(p, raw, hard, sens, scan_um)

    assert looks_like_bruker_spm(p)  # magia de Nanoscope
    with pytest.warns(UserWarning, match="EXPERIMENTAL"):
        data = load_bruker_spm(p)

    assert data.names == ["Height"]
    ch = data["Height"]
    assert ch.shape == (4, 4)
    assert ch.unit == "m"
    assert ch.x_range == pytest.approx(scan_um * 1e-6)  # 5 µm → m
    assert ch.y_range == pytest.approx(scan_um * 1e-6)  # cuadrado: Y == X
    # escala documentada: físico = crudo · hard · sens · (nm→m)
    assert float(ch.data.max()) == pytest.approx(raw.max() * hard * sens * 1e-9)
    assert data.metadata["experimental"] is True and data.metadata["scaled"] is True


def test_bruker_spm_escaneo_no_cuadrado(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Escaneo no cuadrado: X e Y se leen por separado (no se asume X==Y)."""
    raw = np.arange(16, dtype=np.int16).reshape(4, 4)
    p = tmp_path / "rect.spm"
    _write_spm(p, raw, hard=1.0, sens=1.0, scan_um=5.0, scan_y_um=3.0)
    with pytest.warns(UserWarning):
        ch = load_bruker_spm(p)["Height"]
    assert ch.x_range == pytest.approx(5e-6)
    assert ch.y_range == pytest.approx(3e-6)  # antes daba 5e-6 (bug de aspect ratio)


def test_bruker_spm_sin_escala_devuelve_crudo(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Sin ``Z scale`` reconocible → crudo (no inventa calibración), marcado scaled=False."""
    raw = np.arange(16, dtype=np.int16).reshape(4, 4)
    header = (
        "\\*File list\r\n"
        "\\*Ciao image list\r\n"
        "\\Data offset: {off:010d}\r\n"
        "\\Bytes/pixel: 2\r\n"
        "\\Samps/line: 4\r\n"
        "\\Number of lines: 4\r\n"
        '\\@2:Image Data: S [Height] "Height"\r\n'
        "\\*File list end\r\n"
    )
    off = len(header.format(off=0).encode("latin-1"))
    p = tmp_path / "raw.spm"
    p.write_bytes(header.format(off=off).encode("latin-1") + raw.astype("<i2").tobytes())

    with pytest.warns(UserWarning):
        data = load_bruker_spm(p)
    assert data.metadata["scaled"] is False
    assert float(data["Height"].data.max()) == float(raw.max())  # crudo, sin escalar


def test_bruker_spm_decodes_little_endian_pixels(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = np.array([[1, 256], [513, 1024]], dtype=np.int16)
    p = tmp_path / "little.spm"
    _write_spm(p, raw, hard=1.0, sens=1.0, scan_um=1.0)
    with pytest.warns(UserWarning):
        decoded = load_bruker_spm(p)["Height"].data
    assert np.array_equal(decoded, np.flipud(raw).astype(float) * 1e-9)


def test_bruker_spm_enumerates_image_channels(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first = np.array([[1, 2], [3, 4]], dtype="<i2")
    second = np.array([[5, 6], [7, 8]], dtype="<i2")
    template = (
        "\\*File list\r\n"
        "\\*Scanner list\r\n"
        "\\@Sens. Zscale: V 1 nm/V\r\n"
        "\\*Ciao image list\r\n"
        "\\Data offset: {first:010d}\r\n"
        "\\Bytes/pixel: 2\r\n"
        "\\Samps/line: 2\r\n"
        "\\Number of lines: 2\r\n"
        '\\@2:Image Data: S [Height] "Height"\r\n'
        "\\@2:Z scale: V [Zscale] (1 V/LSB)\r\n"
        "\\*Ciao image list\r\n"
        "\\Data offset: {second:010d}\r\n"
        "\\Bytes/pixel: 2\r\n"
        "\\Samps/line: 2\r\n"
        "\\Number of lines: 2\r\n"
        '\\@2:Image Data: S [Phase] "Phase"\r\n'
        "\\@2:Z scale: V [Zscale] (1 V/LSB)\r\n"
        "\\*File list end\r\n"
    )
    offset = len(template.format(first=0, second=0).encode("latin-1"))
    p = tmp_path / "channels.spm"
    p.write_bytes(
        template.format(first=offset, second=offset + first.nbytes).encode("latin-1")
        + first.tobytes()
        + second.tobytes()
    )
    with pytest.warns(UserWarning):
        loaded = load_bruker_spm(p)
    assert loaded.names == ["Height", "Phase"]
    assert np.array_equal(loaded["Phase"].data, np.flipud(second).astype(float) * 1e-9)


def test_bruker_spm_rejects_unsupported_sample_width(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "unsupported.spm"
    _write_spm(p, np.ones((2, 2), dtype=np.int16), hard=1.0, sens=1.0, scan_um=1.0)
    p.write_bytes(p.read_bytes().replace(b"\\Bytes/pixel: 2", b"\\Bytes/pixel: 8"))
    with pytest.warns(UserWarning), pytest.raises(ValueError, match="no soportada"):
        load_bruker_spm(p)


def test_bruker_spm_rejects_truncated_channel(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "truncated.spm"
    _write_spm(p, np.ones((2, 2), dtype=np.int16), hard=1.0, sens=1.0, scan_um=1.0)
    p.write_bytes(p.read_bytes()[:-2])
    with pytest.warns(UserWarning), pytest.raises(ValueError, match="truncado"):
        load_bruker_spm(p)


def test_bruker_spm_uses_versioned_32bit_scale(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = np.array([[1, 256], [513, 1024]], dtype="<i4")
    template = (
        "\\*File list\r\n"
        "\\Version: 0x10000102\r\n"
        "\\*Scanner list\r\n"
        "\\@Sens. ZsensSens: V 10 nm/V\r\n"
        "\\*Ciao scan list\r\n"
        "\\Scan Size: 1 ~m\r\n"
        "\\*Ciao image list\r\n"
        "\\Data offset: {off:010d}\r\n"
        f"\\Data length: {raw.nbytes}\r\n"
        "\\Bytes/pixel: 4\r\n"
        "\\Samps/line: 2\r\n"
        "\\Number of lines: 2\r\n"
        '\\@2:Image Data: S [Height] "Height"\r\n'
        "\\@2:Z scale: V [Sens. ZsensSens] (1 V/LSB) 20 V\r\n"
        "\\*File list end\r\n"
    )
    p = tmp_path / "versioned.spm"
    header = template.format(off=len(template.format(off=0).encode("latin-1"))).encode("latin-1")
    p.write_bytes(header + raw.tobytes())
    with pytest.warns(UserWarning):
        data = load_bruker_spm(p)
    assert np.array_equal(data["Height"].data, np.flipud(raw) * 20 * 10e-9 / 256**4)


def test_bruker_spm_does_not_import_gui(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "nogui.spm"
    _write_spm(p, np.ones((2, 2), dtype=np.int16), hard=1.0, sens=1.0, scan_um=1.0)
    with pytest.warns(UserWarning):
        load_bruker_spm(p)
    assert not any(name.startswith(("PyQt", "pyqtgraph")) for name in sys.modules)

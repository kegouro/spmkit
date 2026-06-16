"""Verificación y trazabilidad del pipeline de procesamiento de archivos ``.nid``.

Permite comprobar que **todos** los datos de un archivo NanoSurf .nid se
extraen, convierten a unidades físicas y almacenan correctamente, rastreando
offsets de bytes y rangos numéricos en cada etapa.

Uso típico::

    from spmkit.core.verify import trace_nid
    trace = trace_nid("archivo.nid")
    print(format_report(trace))
    if not trace.ok:
        raise RuntimeError("Verificación fallida")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from spmkit.core.io.nid import (
    _MARKER,
    _channel_order,
    _decode_header,
    _dtype,
    _parse_ini,
    _to_physical,
)

# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Check:
    """Resultado de una verificación de integridad."""

    name: str
    passed: bool
    detail: str


@dataclass
class ChannelTrace:
    """Información de trazabilidad de un único canal."""

    name: str
    group: str
    dtype: str
    byte_offset: int
    byte_length: int
    points: int
    lines: int
    dim2_unit: str
    raw_min: float
    raw_max: float
    phys_min: float
    phys_max: float
    x_range_m: float
    y_range_m: float
    flipped: bool


@dataclass
class NidTrace:
    """Resultado completo de la trazabilidad de un archivo .nid."""

    path: str
    file_size: int
    marker_offset: int
    binary_bytes: int
    n_sections: int
    n_channels: int
    channels: list[ChannelTrace] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` si todas las verificaciones pasan."""
        return all(c.passed for c in self.checks)


# ---------------------------------------------------------------------------
# Función principal de trazabilidad
# ---------------------------------------------------------------------------


def trace_nid(path: str | Path) -> NidTrace:
    """Lee un archivo ``.nid`` y devuelve una traza completa de integridad.

    Parameters
    ----------
    path:
        Ruta al archivo ``.nid``.

    Returns
    -------
    NidTrace
        Objeto con offsets, rangos, y lista de verificaciones.
    """
    path = Path(path)
    blob = path.read_bytes()
    file_size = len(blob)

    checks: list[Check] = []
    channels: list[ChannelTrace] = []

    # ------------------------------------------------------------------
    # Check 1: marcador #! presente
    # ------------------------------------------------------------------
    marker_offset = blob.find(_MARKER)
    marker_ok = marker_offset != -1
    checks.append(
        Check(
            name="marcador #! presente",
            passed=marker_ok,
            detail=f"offset={marker_offset}" if marker_ok else "no encontrado",
        )
    )

    if not marker_ok:
        return NidTrace(
            path=str(path),
            file_size=file_size,
            marker_offset=-1,
            binary_bytes=0,
            n_sections=0,
            n_channels=0,
            channels=channels,
            checks=checks,
        )

    bin_start = marker_offset + len(_MARKER)
    binary_bytes = file_size - bin_start

    # ------------------------------------------------------------------
    # Check 2: header decodifica (UTF-8/latin-1)
    # ------------------------------------------------------------------
    try:
        header_text = _decode_header(blob[:marker_offset])
        header_ok = True
        header_detail = f"{len(header_text)} caracteres"
    except Exception as exc:  # noqa: BLE001
        header_ok = False
        header_text = ""
        header_detail = str(exc)

    checks.append(
        Check(
            name="header decodifica (UTF-8/latin-1)",
            passed=header_ok,
            detail=header_detail,
        )
    )

    if not header_ok:
        return NidTrace(
            path=str(path),
            file_size=file_size,
            marker_offset=marker_offset,
            binary_bytes=binary_bytes,
            n_sections=0,
            n_channels=0,
            channels=channels,
            checks=checks,
        )

    sections = _parse_ini(header_text)
    n_sections = len(sections)

    # ------------------------------------------------------------------
    # Check 3: sección [DataSet] presente
    # ------------------------------------------------------------------
    dataset_ok = "DataSet" in sections
    checks.append(
        Check(
            name="sección [DataSet] presente",
            passed=dataset_ok,
            detail=(
                f"secciones disponibles: {list(sections.keys())[:10]}"
                if not dataset_ok
                else f"{n_sections} secciones en total"
            ),
        )
    )

    if not dataset_ok:
        return NidTrace(
            path=str(path),
            file_size=file_size,
            marker_offset=marker_offset,
            binary_bytes=binary_bytes,
            n_sections=n_sections,
            n_channels=0,
            channels=channels,
            checks=checks,
        )

    order = _channel_order(sections["DataSet"])
    n_channels = len(order)

    # ------------------------------------------------------------------
    # Recorrer cada canal y construir su ChannelTrace
    # ------------------------------------------------------------------
    offset = bin_start
    total_block_bytes = 0
    all_finite = True
    phys_in_range = True
    axes_positive = True

    for sec_name in order:
        sec = sections.get(sec_name)
        if sec is None:
            continue

        points = int(sec.get("Points", "0"))
        lines = int(sec.get("Lines", "0"))
        dt = _dtype(sec)
        bits = int(sec.get("SaveBits", "32"))
        signed = sec.get("SaveSign", "Signed").lower() == "signed"
        count = points * lines
        byte_len = count * dt.itemsize

        total_block_bytes += byte_len

        # Leer bloque raw
        if offset + byte_len <= file_size:
            raw = np.frombuffer(blob, dtype=dt, count=count, offset=offset).reshape(lines, points)
            raw_min = float(raw.min())
            raw_max = float(raw.max())

            phys = _to_physical(raw, sec, bits, signed)

            if not np.all(np.isfinite(phys)):
                all_finite = False

            dim2_min = float(sec.get("Dim2Min", "0"))
            dim2_range = float(sec.get("Dim2Range", "1"))
            lo = min(dim2_min, dim2_min + dim2_range) - abs(dim2_range) * 1e-9
            hi = max(dim2_min, dim2_min + dim2_range) + abs(dim2_range) * 1e-9
            if np.any(np.isfinite(phys)) and (
                float(np.nanmin(phys)) < lo or float(np.nanmax(phys)) > hi
            ):
                phys_in_range = False

            phys_min = float(np.nanmin(phys))
            phys_max = float(np.nanmax(phys))
        else:
            raw_min = raw_max = 0.0
            phys_min = phys_max = 0.0

        dim1_name = sec.get("Dim1Name", "")
        is_image = dim1_name.startswith("Y")
        flipped = is_image

        x_range = float(sec.get("Dim0Range", "0"))
        y_range = float(sec.get("Dim1Range", "0"))

        if is_image and (x_range <= 0 or y_range <= 0):
            axes_positive = False

        channels.append(
            ChannelTrace(
                name=sec.get("Dim2Name", sec_name),
                group=sec.get("Frame", ""),
                dtype=str(dt),
                byte_offset=offset,
                byte_length=byte_len,
                points=points,
                lines=lines,
                dim2_unit=sec.get("Dim2Unit", ""),
                raw_min=raw_min,
                raw_max=raw_max,
                phys_min=phys_min,
                phys_max=phys_max,
                x_range_m=x_range,
                y_range_m=y_range,
                flipped=flipped,
            )
        )
        offset += byte_len

    # ------------------------------------------------------------------
    # Check 4: suma de bloques == binary_bytes
    # ------------------------------------------------------------------
    budget_ok = total_block_bytes == binary_bytes
    checks.append(
        Check(
            name="suma de bloques binarios == bytes tras el marcador",
            passed=budget_ok,
            detail=f"bloques={total_block_bytes} B, disponibles={binary_bytes} B",
        )
    )

    # ------------------------------------------------------------------
    # Check 5: ningún canal excede el tamaño del archivo
    # ------------------------------------------------------------------
    max_end = max((ch.byte_offset + ch.byte_length for ch in channels), default=0)
    no_overflow = max_end <= file_size
    checks.append(
        Check(
            name="ningún canal excede el tamaño del archivo",
            passed=no_overflow,
            detail=f"fin máximo={max_end}, tamaño archivo={file_size}",
        )
    )

    # ------------------------------------------------------------------
    # Check 6: todos los datos finitos
    # ------------------------------------------------------------------
    checks.append(
        Check(
            name="todos los datos finitos (sin NaN/Inf)",
            passed=all_finite,
            detail="OK" if all_finite else "se encontraron NaN o Inf",
        )
    )

    # ------------------------------------------------------------------
    # Check 7: phys dentro de [Dim2Min, Dim2Min+Dim2Range] por canal
    # ------------------------------------------------------------------
    checks.append(
        Check(
            name="phys dentro de [Dim2Min, Dim2Min+Dim2Range]",
            passed=phys_in_range,
            detail="OK" if phys_in_range else "valores fuera del rango declarado",
        )
    )

    # ------------------------------------------------------------------
    # Check 8: ejes X/Y > 0 para canales de imagen
    # ------------------------------------------------------------------
    checks.append(
        Check(
            name="ejes X/Y > 0 para canales de imagen",
            passed=axes_positive,
            detail="OK" if axes_positive else "algún eje de imagen tiene rango ≤ 0",
        )
    )

    return NidTrace(
        path=str(path),
        file_size=file_size,
        marker_offset=marker_offset,
        binary_bytes=binary_bytes,
        n_sections=n_sections,
        n_channels=n_channels,
        channels=channels,
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Reporte en texto
# ---------------------------------------------------------------------------


def format_report(trace: NidTrace) -> str:
    """Genera un reporte legible de la traza de un archivo .nid.

    Parameters
    ----------
    trace:
        Objeto :class:`NidTrace` devuelto por :func:`trace_nid`.

    Returns
    -------
    str
        Reporte en texto plano con encabezado, tabla de canales y checks.
    """
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"TRAZA .nid: {trace.path}")
    lines.append("=" * 72)
    lines.append(f"  Tamaño archivo : {trace.file_size:,} bytes")
    lines.append(f"  Offset marcador: {trace.marker_offset}")
    lines.append(f"  Bytes binarios : {trace.binary_bytes:,}")
    lines.append(f"  Secciones INI  : {trace.n_sections}")
    lines.append(f"  Canales        : {trace.n_channels}")
    lines.append("")

    if trace.channels:
        lines.append("CANALES:")
        hdr = (
            f"  {'Canal':<20} {'Offset':>10} {'Bytes':>10} {'Forma':>9} "
            f"{'Unidad':>6} {'Raw min':>12} {'Raw max':>12} "
            f"{'Fís min':>14} {'Fís max':>14} {'Volt':>5}"
        )
        lines.append(hdr)
        lines.append("  " + "-" * (len(hdr) - 2))
        for ch in trace.channels:
            lines.append(
                f"  {ch.name:<20} {ch.byte_offset:>10,} {ch.byte_length:>10,} "
                f"{ch.lines}×{ch.points:>5} {ch.dim2_unit:>6} "
                f"{ch.raw_min:>12.4g} {ch.raw_max:>12.4g} "
                f"{ch.phys_min:>14.6g} {ch.phys_max:>14.6g} "
                f"{'Sí':>5}"
                if ch.flipped
                else f"  {ch.name:<20} {ch.byte_offset:>10,} {ch.byte_length:>10,} "
                f"{ch.lines}×{ch.points:>5} {ch.dim2_unit:>6} "
                f"{ch.raw_min:>12.4g} {ch.raw_max:>12.4g} "
                f"{ch.phys_min:>14.6g} {ch.phys_max:>14.6g} "
                f"{'No':>5}"
            )
        lines.append("")

    lines.append("VERIFICACIONES:")
    for chk in trace.checks:
        mark = "✓" if chk.passed else "✗"
        lines.append(f"  [{mark}] {chk.name}")
        lines.append(f"       → {chk.detail}")
    lines.append("")
    estado = "VERIFICACIÓN OK" if trace.ok else "VERIFICACIÓN FALLIDA"
    lines.append(f"  {estado}")
    lines.append("=" * 72)
    return "\n".join(lines)

"""Lector de curvas/mapas de fuerza JPK en formato **TIFF** (no el contenedor ZIP).

Algunos exports de JPK guardan las curvas de fuerza como un TIFF multipágina con tags
propietarios (código ≥ 32768), distinto del ``.jpk-force`` ZIP que lee ``afmformats``. Cada
página es un ``(segmento × canal)``: los canales (``Height``, ``Vertical Deflection``…) se
guardan como enteros crudos y **cada *slot* de calibración es una conversión lineal directa
desde el crudo**: ``físico = crudo · multiplicador + offset``. En los tags, la unidad de un
slot (``"N"``, ``"m"``, ``"V"``) está en el código ``X`` y le siguen ``LinearScaling`` (``X+1``),
el multiplicador (``X+2``) y el offset (``X+3``).

Conversión validada contra la física del archivo de referencia (fuerza en nN, altura en µm,
deflexión en nm, y ``k = mult_fuerza / mult_distancia`` da una constante de resorte plausible).
Requiere el extra ``jpk`` (``tifffile``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

#: Tag propietario de JPK presente en la primera página (para reconocer el formato).
_JPK_TAG = 32768
#: Tag con el nombre visible del canal de cada página.
_CHANNEL_NAME_TAG = 32850
#: Canal de fuerza (deflexión vertical) y candidatos de altura para la separación.
_FORCE_CHANNEL = "Vertical Deflection"
_HEIGHT_CHANNELS = ("Height (measured)", "Height")


def looks_like_jpk_tiff(path: str | Path) -> bool:
    """``True`` si ``path`` es un TIFF con tags JPK (reconoce el formato sin extensión)."""
    try:
        with open(path, "rb") as fh:
            if fh.read(2) not in (b"II", b"MM"):  # magia TIFF
                return False
        import tifffile

        with tifffile.TiffFile(path) as tf:
            page_or_frame = tf.pages[0]
            page = (
                page_or_frame.aspage()
                if isinstance(page_or_frame, tifffile.TiffFrame)
                else page_or_frame
            )
            return _JPK_TAG in {t.code for t in page.tags}
    except Exception:  # noqa: BLE001 - cualquier fallo = no es un JPK-TIFF legible
        return False


def _slots(tags: dict[int, Any]) -> dict[str, tuple[float, float]]:
    """``{unidad: (multiplicador, offset)}`` de los slots de calibración lineales de la página."""
    out: dict[str, tuple[float, float]] = {}
    for code, val in tags.items():
        if (
            isinstance(val, str)
            and val in ("N", "m", "V")
            and tags.get(code + 1) == "LinearScaling"
        ):
            try:
                out[val] = (float(tags[code + 2]), float(tags[code + 3]))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _read_pages(path: str | Path) -> list[dict[str, Any]]:
    """Materializa (nombre, array crudo, slots por unidad) de cada página CON DATOS de canal.

    Todo se lee **dentro** del contexto de ``tifffile`` (los valores de tag son perezosos).
    """
    import tifffile

    pages: list[dict[str, Any]] = []
    with tifffile.TiffFile(path) as tf:
        for page_or_frame in tf.pages:
            page = (
                page_or_frame.aspage()
                if isinstance(page_or_frame, tifffile.TiffFrame)
                else page_or_frame
            )
            tags = {t.code: t.value for t in page.tags}
            name = str(tags.get(_CHANNEL_NAME_TAG, ""))
            slots = _slots(tags)
            if name and name != "None" and slots:  # descarta el preview (sin nombre/slots)
                pages.append({"name": name, "raw": np.asarray(page.asarray()), "slots": slots})
    return pages


def _physical(page: dict[str, Any], unit: str) -> np.ndarray | None:
    slot = page["slots"].get(unit)
    if slot is None:
        return None
    mult, offset = slot
    return page["raw"].astype(np.float64) * mult + offset


def load_jpk_tiff(path: str | Path) -> Any:
    """Lee un TIFF de fuerza JPK como :class:`ForceVolume` (una curva por fila del mapa).

    Agrupa las páginas en segmentos (extend/retract) por el ciclo de nombres de canal y, para
    cada curva, arma ``fuerza`` (N) desde la deflexión vertical y ``separación`` = altura −
    deflexión (ambas en m), con la conversión lineal directa de JPK.
    """
    from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume

    data = _read_pages(path)
    if not data:
        raise ValueError(f"JPK-TIFF sin páginas de canal reconocibles: {Path(path).name}")

    # Agrupar en segmentos: un canal que se repite abre un segmento nuevo.
    segments: list[dict[str, dict[str, Any]]] = []
    current: dict[str, dict[str, Any]] = {}
    for page in data:
        if page["name"] in current:
            segments.append(current)
            current = {}
        current[page["name"]] = page
    if current:
        segments.append(current)

    # Orden JPK: segmento 0 = aproximación (extend), 1 = retracción.
    seg_meta = [("extend", "approach"), ("retract", "retract")]
    n_curves = int(next(iter(segments[0].values()))["raw"].shape[0])

    curves = []
    for r in range(n_curves):
        seg_objs = []
        for i, seg in enumerate(segments):
            force_page = seg.get(_FORCE_CHANNEL)
            height_page = next((seg[h] for h in _HEIGHT_CHANNELS if h in seg), None)
            if force_page is None or height_page is None:
                continue
            force = _physical(force_page, "N")
            deflection = _physical(force_page, "m")
            height = _physical(height_page, "m")
            if force is None or deflection is None or height is None:
                continue
            kind, direction = seg_meta[i] if i < len(seg_meta) else ("pause", "static")
            seg_objs.append(
                ForceSegment(
                    segment_type=kind,  # type: ignore[arg-type]
                    direction=direction,
                    raw_height=height[r],
                    raw_deflection=deflection[r],
                    deflection=deflection[r],
                    force=force[r],
                    separation=height[r] - deflection[r],
                    state="force_n",
                    metadata={"format": "jpk-tiff"},
                )
            )
        if seg_objs:
            curves.append(ForceCurve(segments=tuple(seg_objs), index=r))

    if not curves:
        raise ValueError(f"JPK-TIFF sin curvas de fuerza válidas: {Path(path).name}")
    return ForceVolume.from_curves(
        tuple(curves), grid_shape=(1, len(curves)), x_range=1e-6, y_range=1e-6
    )


class JpkTiffReader:
    """Adaptador de :func:`load_jpk_tiff` al contrato de lector (detección por contenido).

    JPK-TIFF no se distingue por extensión (el export suele venir sin ella), así que
    ``load_any`` lo elige por :func:`looks_like_jpk_tiff` cuando ninguna extensión coincide.
    """

    extensions: tuple[str, ...] = ()  # se reconoce por contenido, no por sufijo

    def inspect(self, path: str | Path) -> Any:
        from spmkit.core.plugins.contracts import DatasetInfo

        return DatasetInfo(path=Path(path), format="jpk-tiff", kinds=("force",))

    def load(self, path: str | Path, kind: Any = None) -> Any:
        return load_jpk_tiff(path)

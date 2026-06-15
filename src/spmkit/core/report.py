"""Generación de reportes HTML autocontenidos (imprimibles a PDF).

Embebe la figura como PNG en base64, junto con tablas de rugosidad/KPFM y
metadatos del barrido. El HTML es autocontenido (un solo archivo) y se puede
"Imprimir → Guardar como PDF" desde cualquier navegador.

Requiere el extra ``report`` (``pip install 'spmkit[report]'``).
"""

from __future__ import annotations

import base64
import io
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from spmkit.core.models import SPMChannel, SPMData
from spmkit.core.viz import FigureSpec
from spmkit.core.viz.figure import render_channel

_TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Reporte spmkit — {{ source }}</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 820px; color: #1a1a1a; }
  h1 { font-size: 1.4rem; } h2 { font-size: 1.05rem; margin-top: 1.6rem; }
  table { border-collapse: collapse; margin: .5rem 0; }
  td, th { border: 1px solid #ccc; padding: .25rem .6rem; text-align: left; }
  th { background: #f3f3f3; }
  img { max-width: 100%; border: 1px solid #ddd; }
  .meta { color: #555; font-size: .85rem; }
  footer { margin-top: 2rem; color: #888; font-size: .8rem; }
</style></head><body>
<h1>Reporte de análisis SPM</h1>
<p class="meta">Archivo: <b>{{ source }}</b> · Canal: <b>{{ channel }}</b> · Generado por spmkit</p>
<h2>Imagen</h2>
<img src="data:image/png;base64,{{ image }}" alt="figura">
{% for section in sections %}
<h2>{{ section.title }}</h2>
<table><tr><th>Parámetro</th><th>Valor</th></tr>
{% for k, v in section.rows %}<tr><td>{{ k }}</td><td>{{ v }}</td></tr>{% endfor %}
</table>
{% endfor %}
<footer>spmkit · SPM Lab UTFSM</footer>
</body></html>"""


def _fmt(value: Any) -> str:
    return f"{value:.4g}" if isinstance(value, float) else str(value)


def _rows(result: Any) -> list[tuple[str, str]]:
    data = asdict(result) if is_dataclass(result) and not isinstance(result, type) else dict(result)
    return [(k, _fmt(v)) for k, v in data.items()]


def build_report(
    data: SPMData,
    channel: SPMChannel,
    results: dict[str, Any],
    path: str | Path,
    spec: FigureSpec | None = None,
) -> Path:
    """Genera un reporte HTML del canal con las secciones de ``results``.

    Args:
        data: Archivo SPM de origen (para metadatos).
        channel: Canal mostrado en la figura.
        results: ``{título_sección: resultado_dataclass/dict}``.
        path: Ruta de salida ``.html``.
        spec: Estilo de la figura (opcional).
    """
    try:
        import matplotlib.pyplot as plt
        from jinja2 import Template
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "Los reportes requieren matplotlib + jinja2. Instala: pip install 'spmkit[report]'"
        ) from exc

    fig = render_channel(channel, spec)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    sections = [{"title": title, "rows": _rows(res)} for title, res in results.items()]
    html = Template(_TEMPLATE).render(
        source=Path(data.source_path).name or "—",
        channel=channel.name,
        image=image_b64,
        sections=sections,
    )
    path = Path(path)
    path.write_text(html, encoding="utf-8")
    return path

"""Informe magistral de espectroscopía de fuerza — HTML, LaTeX y PDF.

Toma un ``ForceVolume`` (o una carpeta procesada), calcula los mapas de propiedades
mecánicas, elige una curva representativa, arma figuras de publicación (mapas, curva
+ ajuste, histogramas) y ensambla un informe profesional. Genera:

* **HTML** autocontenido (PNG embebidos en base64) — abre en cualquier navegador.
* **LaTeX** (``.tex``) — editable, con ``\\includegraphics`` de las figuras.
* **PDF** — compilando el LaTeX con ``tectonic``/``pdflatex``/``xelatex`` si están.

Reutiliza el motor vectorizado (:mod:`forcevolume_fast`) y las figuras de
:mod:`spmkit.core.viz`. Requiere el extra ``report`` (matplotlib + jinja2).
"""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.analysis.forcevolume_fast import elasticity_map
from spmkit.core.models import ForceVolume
from spmkit.core.viz.maps import _MAP_LABELS, save_property_maps

#: Propiedades a resumir en el informe (clave → (etiqueta, factor a unidad display)).
_REPORT_PROPS = (
    ("young_modulus", "Módulo de Young", 1e-3, "kPa"),
    ("adhesion", "Adhesión", 1e9, "nN"),
    ("dissipation", "Disipación", 1e15, "fJ"),
    ("max_force", "Fuerza máxima", 1e9, "nN"),
    ("max_indentation", "Indentación máx", 1e9, "nm"),
    ("r_squared", "R² del ajuste", 1.0, ""),
)


def _which_latex() -> list[str] | None:
    """Comando de compilación LaTeX→PDF disponible (tectonic preferido), o ``None``."""
    if shutil.which("tectonic"):
        return ["tectonic", "--keep-logs", "--outdir"]
    if shutil.which("pdflatex"):
        return ["pdflatex", "-interaction=nonstopmode", "-output-directory"]
    if shutil.which("xelatex"):
        return ["xelatex", "-interaction=nonstopmode", "-output-directory"]
    return None


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _latexify(text: str, escape: bool = False) -> str:
    """Convierte unicode problemático a comandos LaTeX (y escapa especiales si ``escape``)."""
    if escape:
        for ch in "&%#_":
            text = text.replace(ch, "\\" + ch)
    return (
        text.replace("×", r"$\times$")
        .replace("±", r"$\pm$")
        .replace("²", r"\textsuperscript{2}")
        .replace("·", r"$\cdot$")
        .replace("µ", r"$\mu$")
        .replace("—", "---")
    )


def _representative_index(modulus: np.ndarray) -> int:
    """Índice (flat) de la curva cuyo módulo está más cerca de la mediana."""
    flat = modulus.ravel()
    finite = np.isfinite(flat)
    if not finite.any():
        return 0
    median = float(np.median(flat[finite]))
    diff = np.where(finite, np.abs(flat - median), np.inf)
    return int(np.argmin(diff))


def _fit_context(
    volume: ForceVolume, index: int, model: str, tip_radius: float, poisson: float
) -> tuple[Any, dict[str, Any]]:
    """Corre el pipeline en una curva y devuelve ``(curva_calibrada, ctx)``."""
    from spmkit.core.pipeline import Recipe, Step, run

    recipe = Recipe(
        steps=(
            Step(op="calibrate"),
            Step(op="find_contact_point"),
            Step(
                op="fit_elasticity",
                params={"model": model, "tip_radius": tip_radius, "poisson": poisson},
                condition="contact_detected",
            ),
        )
    )
    return run(recipe, volume.curve(index))


def _histograms_figure(result: Any, path: Path, dpi: int = 150) -> None:
    """Panel de histogramas de las propiedades finitas."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    keys = [k for k, *_ in _REPORT_PROPS if k in result.maps and np.isfinite(result.maps[k]).any()]
    n = len(keys)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols)) if n else 1
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    label = {k: (lbl, sc, u) for k, lbl, sc, u in _REPORT_PROPS}
    for ax, key in zip(axes.ravel(), keys, strict=False):
        ax.axis("on")
        vals = result.maps[key].ravel()
        vals = vals[np.isfinite(vals)] * label[key][1]
        ax.hist(vals, bins=30, color="#2DD4BF", edgecolor="#0E9488")
        unit = f" ({label[key][2]})" if label[key][2] else ""
        ax.set_xlabel(f"{label[key][0]}{unit}")
        ax.set_ylabel("cuentas")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _stats_rows(result: Any) -> list[dict[str, str]]:
    """Filas de la tabla resumen: propiedad, mediana ± σ, rango, N."""
    rows = []
    for key, label, scale, unit in _REPORT_PROPS:
        if key not in result.maps:
            continue
        s = result.stats(key)
        if not np.isfinite(s["median"]):
            continue
        u = f" {unit}" if unit else ""
        rows.append(
            {
                "prop": label,
                "median": f"{s['median'] * scale:.3g} ± {s['std'] * scale:.2g}{u}",
                "range": f"[{s['min'] * scale:.3g}, {s['max'] * scale:.3g}]{u}",
                "n": str(s["n"]),
            }
        )
    return rows


def build_force_report(
    volume: ForceVolume,
    out_path: str | Path,
    *,
    title: str = "Informe de espectroscopía de fuerza",
    source_name: str = "",
    model: str = "sphere",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    backend: str = "cpu",
    formats: tuple[str, ...] = ("html", "pdf"),
) -> dict[str, Path]:
    """Genera el informe de un force-volume en los ``formats`` pedidos.

    Args:
        out_path: ruta base (sin extensión), p. ej. ``informe`` → ``informe.html``.
        formats: subconjunto de ``("html", "latex", "pdf")``. ``pdf`` implica ``latex``.

    Returns:
        Diccionario ``formato → ruta`` de los archivos producidos.
    """
    try:
        from jinja2 import Environment
    except ImportError as exc:  # pragma: no cover - depende del extra report
        raise ImportError("El informe requiere jinja2 + matplotlib (extra 'report').") from exc

    out = Path(out_path).with_suffix("")
    assets = out.parent / f"{out.name}_assets"
    assets.mkdir(parents=True, exist_ok=True)

    result = elasticity_map(
        volume, tip_radius=tip_radius, poisson=poisson, model=model, backend=backend
    )
    rows, cols = volume.grid_shape

    # --- figuras ---
    map_keys = [k for k in _MAP_LABELS if k in result.maps and np.isfinite(result.maps[k]).any()]
    maps_png = assets / "mapas.png"
    save_property_maps(result.maps, maps_png, keys=map_keys, title=source_name or "")

    idx = _representative_index(result.maps["young_modulus"])
    curve, ctx = _fit_context(volume, idx, model, tip_radius, poisson)
    from spmkit.core.viz import save_force_curve

    curve_png = assets / "curva_representativa.png"
    save_force_curve(curve, ctx, curve_png)

    hist_png = assets / "histogramas.png"
    _histograms_figure(result, hist_png)

    ctx_report: dict[str, Any] = {
        "title": title,
        "source": source_name or "—",
        "grid": f"{rows}×{cols}",
        "n_curves": volume.n_curves,
        "n_ok": result.n_ok,
        "n_failed": result.n_failed,
        "model": model,
        "tip_radius_nm": tip_radius * 1e9,
        "poisson": poisson,
        "backend": backend,
        "rep_index": idx,
        "stats": _stats_rows(result),
    }

    produced: dict[str, Path] = {}

    if "html" in formats:
        env = Environment(autoescape=False)  # noqa: S701 - contenido propio, no entrada externa
        html = env.from_string(_HTML_TEMPLATE).render(
            maps_b64=_b64(maps_png),
            curve_b64=_b64(curve_png),
            hist_b64=_b64(hist_png),
            **ctx_report,
        )
        html_path = out.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        produced["html"] = html_path

    if "latex" in formats or "pdf" in formats:
        # Delimitadores \VAR{} / \BLOCK{} para no chocar con las llaves de LaTeX.
        env_tex = Environment(  # noqa: S701 - contenido propio
            variable_start_string=r"\VAR{",
            variable_end_string="}",
            block_start_string=r"\BLOCK{",
            block_end_string="}",
            autoescape=False,
        )
        tex_ctx = dict(ctx_report)
        tex_ctx["grid"] = _latexify(str(ctx_report["grid"]))
        tex_ctx["source"] = _latexify(str(ctx_report["source"]), escape=True)
        tex_ctx["title"] = _latexify(str(ctx_report["title"]), escape=True)
        tex_ctx["model"] = _latexify(str(ctx_report["model"]))
        tex_ctx["backend"] = _latexify(str(ctx_report["backend"]))
        tex_ctx["stats"] = [
            {
                "prop": _latexify(r["prop"]),
                "median": _latexify(r["median"]),
                "range": _latexify(r["range"]),
                "n": r["n"],
            }
            for r in ctx_report["stats"]
        ]
        tex = env_tex.from_string(_LATEX_TEMPLATE).render(
            maps_png=maps_png.name,
            curve_png=curve_png.name,
            hist_png=hist_png.name,
            **tex_ctx,
        )
        tex_path = out.with_suffix(".tex")
        tex_path.write_text(tex, encoding="utf-8")
        # Las figuras deben estar junto al .tex para \includegraphics.
        for fig in (maps_png, curve_png, hist_png):
            shutil.copy(fig, out.parent / fig.name)
        produced["latex"] = tex_path

    if "pdf" in formats:
        pdf_path = _compile_pdf(tex_path, out.parent)
        if pdf_path is not None:
            produced["pdf"] = pdf_path

    return produced


def _compile_pdf(tex_path: Path, out_dir: Path) -> Path | None:
    """Compila ``tex_path`` a PDF con la cadena LaTeX disponible; ``None`` si no hay."""
    cmd = _which_latex()
    if cmd is None:
        return None
    try:
        subprocess.run(
            [*cmd, str(out_dir), str(tex_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    pdf = tex_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None


_HTML_TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{{ title }}</title>
<style>
 body{font-family:system-ui,-apple-system,sans-serif;margin:2rem auto;max-width:900px;color:#14181f;}
 h1{font-size:1.6rem;border-bottom:3px solid #2DD4BF;padding-bottom:.4rem;}
 h2{font-size:1.15rem;margin-top:2rem;color:#0E9488;}
 table{border-collapse:collapse;width:100%;margin:.6rem 0;font-size:.92rem;}
 td,th{border:1px solid #d5dbe2;padding:.35rem .7rem;text-align:left;}
 th{background:#eef7f5;} tr:nth-child(even){background:#fafbfc;}
 img{max-width:100%;border:1px solid #e3e7ec;border-radius:6px;margin:.4rem 0;}
 .summary{display:flex;gap:1rem;flex-wrap:wrap;margin:.6rem 0;}
 .card{background:#f4f8f7;border:1px solid #d8ebe7;border-radius:8px;padding:.6rem 1rem;flex:1;min-width:150px;}
 .card b{display:block;font-size:1.3rem;color:#0E9488;} .card span{color:#5a626b;font-size:.82rem;}
 footer{margin-top:2.5rem;color:#98a1ab;font-size:.8rem;border-top:1px solid #e3e7ec;padding-top:.6rem;}
</style></head><body>
<h1>{{ title }}</h1>
<p style="color:#5a626b">Fuente: <b>{{ source }}</b> · Generado por spmkit / Fathom</p>
<div class="summary">
 <div class="card"><b>{{ n_curves }}</b><span>curvas ({{ grid }})</span></div>
 <div class="card"><b>{{ n_ok }}</b><span>ajustadas OK · {{ n_failed }} fallidas</span></div>
 <div class="card"><b>{{ model }}</b><span>modelo · R = {{ '%.1f'|format(tip_radius_nm) }} nm · ν = {{ poisson }}</span></div>
</div>
<h2>Estadística de propiedades mecánicas</h2>
<table><tr><th>Propiedad</th><th>Mediana ± σ</th><th>Rango</th><th>N</th></tr>
{% for r in stats %}<tr><td>{{ r.prop }}</td><td>{{ r.median }}</td><td>{{ r.range }}</td><td>{{ r.n }}</td></tr>{% endfor %}
</table>
<h2>Mapas de propiedades</h2>
<img src="data:image/png;base64,{{ maps_b64 }}" alt="mapas">
<h2>Distribuciones</h2>
<img src="data:image/png;base64,{{ hist_b64 }}" alt="histogramas">
<h2>Curva representativa (índice {{ rep_index }})</h2>
<img src="data:image/png;base64,{{ curve_b64 }}" alt="curva">
<footer>spmkit · Fathom — SPM Lab UTFSM · motor de cálculo: {{ backend }}</footer>
</body></html>"""


_LATEX_TEMPLATE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish]{babel}
\usepackage{graphicx,booktabs,geometry,xcolor}
\geometry{margin=2.3cm}
\definecolor{teal}{HTML}{0E9488}
\usepackage{titlesec}
\titleformat{\section}{\large\bfseries\color{teal}}{}{0em}{}
\begin{document}
\begin{center}
{\LARGE\bfseries \VAR{title}}\\[2pt]
{\color{teal!70!black}\rule{\linewidth}{2pt}}\\[4pt]
Fuente: \textbf{\VAR{source}} \quad|\quad Generado por spmkit / Fathom
\end{center}
\vspace{4pt}
\begin{center}\small
\begin{tabular}{cccc}
\toprule
Curvas & Grilla & Ajustadas OK & Modelo \\ \midrule
\VAR{n_curves} & \VAR{grid} & \VAR{n_ok} / \VAR{n_curves} & \VAR{model} ($R=\VAR{'%.1f'|format(tip_radius_nm)}$\,nm, $\nu=\VAR{poisson}$) \\
\bottomrule
\end{tabular}
\end{center}
\section*{Estadística de propiedades mecánicas}
\begin{center}
\begin{tabular}{lrrr}
\toprule
Propiedad & Mediana $\pm\,\sigma$ & Rango & N \\ \midrule
\BLOCK{for r in stats}\VAR{r.prop} & \VAR{r.median} & \VAR{r.range} & \VAR{r.n} \\
\BLOCK{endfor}\bottomrule
\end{tabular}
\end{center}
\section*{Mapas de propiedades}
\begin{center}\includegraphics[width=\linewidth]{\VAR{maps_png}}\end{center}
\section*{Distribuciones}
\begin{center}\includegraphics[width=\linewidth]{\VAR{hist_png}}\end{center}
\section*{Curva representativa (\'indice \VAR{rep_index})}
\begin{center}\includegraphics[width=0.7\linewidth]{\VAR{curve_png}}\end{center}
\vfill
\noindent\rule{\linewidth}{0.4pt}\\
{\small spmkit $\cdot$ Fathom --- SPM Lab UTFSM $\cdot$ motor: \VAR{backend}}
\end{document}"""

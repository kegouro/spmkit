"""Figura de publicación de una curva de fuerza con su ajuste (matplotlib).

Complementa las figuras de imagen (``figure.py``): dibuja approach/retract, la línea
de ajuste, el punto de contacto y anota módulo ± σ y R². Fondo claro de publicación,
independiente del tema oscuro de la GUI. Requiere el extra ``viz``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spmkit.core.analysis.forcecurve import display_axis
from spmkit.core.models import ForceCurve

_NM = 1e9
_NN = 1e9


def _modulus_label(ctx: dict[str, Any]) -> str:
    e = ctx.get("young_modulus")
    if not isinstance(e, (int, float)) or not np.isfinite(e):
        return ""
    es = ctx.get("young_modulus_std", 0.0) or 0.0
    scale, unit = 1.0, "Pa"
    for s, u in ((1e9, "GPa"), (1e6, "MPa"), (1e3, "kPa")):
        if abs(e) >= s:
            scale, unit = s, u
            break
    r2 = ctx.get("r_squared")
    r2_txt = f"\nR² = {r2:.4f}" if isinstance(r2, (int, float)) and np.isfinite(r2) else ""
    return f"E = {e / scale:.3g} ± {es / scale:.2g} {unit}{r2_txt}"


def render_force_curve(
    curve: ForceCurve,
    ctx: dict[str, Any] | None = None,
    *,
    indentation: bool = False,
    fig: Any = None,
    dpi: int = 300,
) -> Any:
    """Construye una figura matplotlib de ``curve`` y su ajuste (de ``ctx``).

    Args:
        indentation: si ``True``, el eje es la indentación δ (contacto en el origen).
        fig: figura existente para redibujar (lienzo embebido); si ``None`` crea una.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    ctx = ctx or {}
    contact = ctx.get("contact_point")
    offset = float(contact) if (indentation and isinstance(contact, (int, float))) else 0.0

    def axis_of(seg: Any) -> np.ndarray:
        return (display_axis(seg.separation, seg.raw_height) - offset) * _NM

    with plt.rc_context({"font.size": 10, "figure.facecolor": "white", "axes.facecolor": "white"}):
        if fig is None:
            fig, ax = plt.subplots(figsize=(5, 4), dpi=dpi)
        else:
            fig.clear()
            ax = fig.add_subplot(111)

        extend = curve.extend
        retract = curve.retract
        if extend is not None and extend.force is not None:
            ax.plot(axis_of(extend), extend.force * _NN, color="#4A5A6A", lw=1.4, label="approach")
        if retract is not None and retract.force is not None:
            ax.plot(axis_of(retract), retract.force * _NN, color="#B08A3E", lw=1.2, label="retract")
        fit = ctx.get("fit")
        if fit is not None and getattr(fit, "x_fit", None) is not None and len(fit.x_fit):
            ax.plot(
                (np.asarray(fit.x_fit) - offset) * _NM,
                np.asarray(fit.f_fit) * _NN,
                color="#0E9488",
                lw=2.2,
                label="ajuste",
            )
        if isinstance(contact, (int, float)) and ctx.get("contact_detected", True):
            # Punto de contacto en oro (coherente con la app y el logo Fathom).
            ax.axvline((float(contact) - offset) * _NM, color="#B26A1E", ls="--", lw=0.9)

        ax.set_xlabel("Indentación δ (nm)" if indentation else "Separación (nm)")
        ax.set_ylabel("Fuerza (nN)")
        note = _modulus_label(ctx)
        if note:
            ax.text(
                0.03,
                0.97,
                note,
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                bbox={"boxstyle": "round", "fc": "white", "ec": "#CCCCCC", "alpha": 0.9},
            )
        ax.legend(loc="lower right", framealpha=0.9)
        fig.tight_layout()
    return fig


def save_force_curve(
    curve: ForceCurve,
    ctx: dict[str, Any] | None = None,
    path: str | Path = "force_curve.png",
    *,
    indentation: bool = False,
    dpi: int = 300,
) -> Path:
    """Renderiza y guarda la figura de la curva de fuerza; devuelve la ruta."""
    fig = render_force_curve(curve, ctx, indentation=indentation, dpi=dpi)
    out = Path(path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return out

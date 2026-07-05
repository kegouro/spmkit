"""Inspector — readouts numéricos del ajuste, en mono tabular.

Escucha ``resultsChanged`` del :class:`ForceViewModel` y muestra módulo de Young con
incertidumbre, R², contacto, adhesión, disipación y la calibración usada. El mono
tabular alinea las cifras verticalmente: se leen como el panel de un instrumento.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ForceViewModel

#: Filas del inspector: (clave interna, etiqueta visible).
_ROWS: tuple[tuple[str, str], ...] = (
    ("young", "Módulo E"),
    ("r_squared", "R²"),
    ("contact", "Contacto"),
    ("adhesion", "Adhesión"),
    ("max_force", "Fuerza máx"),
    ("max_indentation", "δ máx"),
    ("dissipation", "Disipación"),
    ("model", "Modelo"),
    ("n_fit", "Puntos"),
    ("spring_constant", "k resorte"),
    ("invols", "InVOLS"),
)

_EMPTY = "—"


def _fmt_modulus(e: float, es: float) -> str:
    """Módulo ± incertidumbre con unidad auto-escalada (Pa→kPa→MPa→GPa)."""
    if not math.isfinite(e):
        return _EMPTY
    scale, unit = 1.0, "Pa"
    for s, u in ((1e9, "GPa"), (1e6, "MPa"), (1e3, "kPa")):
        if abs(e) >= s:
            scale, unit = s, u
            break
    es_txt = f" ± {es / scale:.2g}" if math.isfinite(es) and es > 0 else ""
    return f"{e / scale:.3g}{es_txt} {unit}"


def _fmt_scaled(value: object, scale: float, unit: str, prec: str = ".3g") -> str:
    """Formatea un número escalado (p. ej. N→nN) o ``—`` si no es finito."""
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return _EMPTY
    return f"{float(value) * scale:{prec}} {unit}"


class InspectorPanel(Panel):
    """Panel-dock con los resultados del ajuste de la curva activa."""

    title = "Inspector"

    def __init__(self, vm: ForceViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        self._values: dict[str, QLabel] = {}
        super().__init__(parent)
        vm.resultsChanged.connect(self._on_results)

    def build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        heading = QLabel("Resultados del ajuste")
        heading.setProperty("role", "title")
        lay.addWidget(heading)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for r, (key, label) in enumerate(_ROWS):
            name = QLabel(label)
            name.setProperty("role", "muted")
            value = QLabel(_EMPTY)
            value.setProperty("role", "readout")
            grid.addWidget(name, r, 0)
            grid.addWidget(value, r, 1)
            self._values[key] = value
        lay.addLayout(grid)
        lay.addStretch(1)
        return root

    def _on_results(self, ctx: dict) -> None:
        if not ctx:
            for value in self._values.values():
                value.setText(_EMPTY)
            return
        self._values["young"].setText(
            _fmt_modulus(
                float(ctx.get("young_modulus", float("nan"))),
                float(ctx.get("young_modulus_std", float("nan"))),
            )
        )
        r2 = ctx.get("r_squared")
        self._values["r_squared"].setText(
            f"{float(r2):.4f}" if isinstance(r2, (int, float)) and math.isfinite(r2) else _EMPTY
        )
        self._values["contact"].setText(_fmt_scaled(ctx.get("contact_point"), 1e9, "nm"))
        self._values["adhesion"].setText(_fmt_scaled(ctx.get("adhesion"), 1e9, "nN"))
        self._values["max_force"].setText(_fmt_scaled(ctx.get("max_force"), 1e9, "nN"))
        self._values["max_indentation"].setText(_fmt_scaled(ctx.get("max_indentation"), 1e9, "nm"))
        self._values["dissipation"].setText(_fmt_scaled(ctx.get("dissipation"), 1e15, "fJ"))
        fit = ctx.get("fit")
        self._values["model"].setText(fit.model if fit is not None else _EMPTY)
        self._values["n_fit"].setText(str(fit.n_fit) if fit is not None else _EMPTY)
        self._values["spring_constant"].setText(_fmt_scaled(ctx.get("spring_constant"), 1.0, "N/m"))
        self._values["invols"].setText(_fmt_scaled(ctx.get("invols"), 1e9, "nm/V"))

"""Identidad de marca del producto — el workspace se presenta como **Fathom**.

``spmkit`` es la librería/CLI (motor); **Fathom** es el nombre del workspace de curvas
de fuerza que lo usa, pensado para reemplazar a Nanosurf ANA y JPK Data Processing.
Todo lo visible del producto (título de ventana, "Acerca de", banner) sale de aquí:
para renombrar el producto se cambia una sola constante.

Estética "Instrumento" elevada: grafito + teal de señal + **oro cálido** de acento
(``tokens accent_2``). El logotipo es una curva de fuerza estilizada (línea base →
contacto → carga), ver ``docs/images/brand/``.
"""

from __future__ import annotations

#: Nombre del producto (workspace). El paquete/CLI sigue siendo ``spmkit``.
PRODUCT_NAME = "Fathom"

#: Motor/librería que lo impulsa.
ENGINE_NAME = "spmkit"

#: Lema del producto (juego bilingüe: "a fondo" = en profundidad / a conciencia).
TAGLINE_ES = "Curvas de fuerza, a fondo."
TAGLINE_EN = "Force curves, fathomed."

#: Firma corta para lockups y "Acerca de".
BYLINE = f"powered by {ENGINE_NAME}"

#: Descripción de una línea (para el diálogo "Acerca de").
DESCRIPTION = "Taller de análisis de curvas de fuerza y nanomecánica (AFM/SPM)."

#: Título de la ventana del workspace.
WINDOW_TITLE = f"{PRODUCT_NAME} · {ENGINE_NAME}"

#: Colores de marca (hex), consistentes con :mod:`spmkit.gui.design.tokens`.
BRAND_GRAPHITE = "#0B0E13"
BRAND_TEAL = "#2DD4BF"
BRAND_GOLD = "#E8A94B"

#: Logo-símbolo embebido (curva de fuerza) para el icono de la app, sin depender de
#: un archivo empaquetado. Idéntico a ``docs/images/brand/fathom_mark.svg``.
MARK_SVG = (
    '<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="3.5" y="3.5" width="41" height="41" rx="10" fill="#121821" '
    'stroke="#2A3644" stroke-width="1.2"/>'
    '<path d="M11 33 H22" fill="none" stroke="#4A5765" stroke-width="2.4" stroke-linecap="round"/>'
    '<path d="M22 33 C29 33 33 26 38.5 12" fill="none" stroke="#2DD4BF" stroke-width="2.8" '
    'stroke-linecap="round"/>'
    '<circle cx="22" cy="33" r="2.4" fill="#E8A94B"/></svg>'
)


def about_text() -> str:
    """Texto multilínea para el diálogo 'Acerca de'."""
    return f"{PRODUCT_NAME} — {TAGLINE_ES}\n" f"{DESCRIPTION}\n\n" f"{BYLINE}."

"""Sistema de tokens de diseño — fuente única para QSS, pyqtgraph y matplotlib.

Estética "Instrumento": grafito de precisión con señal teal. Un solo token alimenta
los tres destinos de render (ver :mod:`spmkit.gui.design.theme`), de modo que los
gráficos se sienten nativos del tema y no incrustados.

Jerarquía de color de trazas (v2): **gris = dato crudo, teal = modelo/ajuste**. El
teal se reserva para el ajuste y la traza activa; los datos crudos van en neutrales
fríos para evitar *halation* (halo que difumina el trazo sobre fondo oscuro).
"""

from __future__ import annotations

#: Paletas por modo. Claves con guion_bajo para compatibilidad con string.Template.
_COLORS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0B0E13",  # grafito casi negro
        "surface": "#121821",  # paneles
        "surface_2": "#171F2A",  # controles / barras / dock headers
        "elevated": "#1E2733",  # hover / menús / popovers
        "overlay": "rgba(6, 9, 13, 0.66)",  # modales / backdrop
        "text": "#E8EEF5",
        "text_muted": "#93A0AE",
        "text_faint": "#5C6875",
        "border": "#232C38",
        "border_strong": "#33404F",
        "accent": "#2DD4BF",  # teal de señal
        "accent_press": "#14B8A6",
        "accent_soft": "#0F3A37",
        "on_accent": "#04342C",
        "success": "#4ADE80",
        "warning": "#FBBF24",
        "danger": "#F87171",
    },
    "light": {
        "bg": "#F4F2EC",  # papel cálido
        "surface": "#FFFFFF",
        "surface_2": "#ECE8DF",
        "elevated": "#E4DFD4",
        "overlay": "rgba(20, 18, 12, 0.42)",
        "text": "#181C22",
        "text_muted": "#5A626B",
        "text_faint": "#8A8F98",
        "border": "#DBD6CB",
        "border_strong": "#C4BEB0",
        "accent": "#0E9488",
        "accent_press": "#0B7C72",
        "accent_soft": "#CFEEE9",
        "on_accent": "#FFFFFF",
        "success": "#15803D",
        "warning": "#B45309",
        "danger": "#B91C1C",
    },
}

#: Colores de trazas de datos. Jerarquía v2: crudos neutrales, ajuste en teal.
TRACES: dict[str, str] = {
    "extend": "#C9D3DE",  # dato crudo (neutral frío)
    "retract": "#B49A6E",  # dato crudo (ámbar apagado)
    "fit": "#2DD4BF",  # ajuste = teal (héroe visual)
    "contact": "#2DD4BF",  # marcador de contacto
    "residual": "#33404F",  # residuos (silenciados)
}

#: Paleta categórica (trazas secundarias), colorblind-safe en ambos modos.
CATEGORICAL: tuple[str, ...] = ("#2DD4BF", "#F59E0B", "#A78BFA", "#FB7185")

#: Stacks de fuente nativos refinados.
FONT_UI = '-apple-system, "SF Pro Text", "Segoe UI Variable", "Inter Tight", system-ui, sans-serif'
FONT_MONO = '"SF Mono", "JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", monospace'

#: Escala tipográfica (px).
TYPE_SCALE: dict[str, int] = {
    "xs": 11,
    "sm": 12,
    "base": 13,
    "md": 15,
    "lg": 18,
    "xl": 22,
    "2xl": 28,
}

#: Grilla de espacio (px).
SPACE: dict[str, int] = {"1": 4, "2": 8, "3": 12, "4": 16, "6": 24, "8": 32}

#: Radios (px).
RADIUS: dict[str, int] = {"control": 6, "panel": 10, "modal": 14}

#: Movimiento (ms) y easing.
MOTION: dict[str, object] = {
    "fast": 120,
    "base": 200,
    "enter": 260,
    "easing": "cubic-bezier(0.2, 0.8, 0.2, 1)",
}

MODES: tuple[str, str] = ("dark", "light")


def colors(mode: str = "dark") -> dict[str, str]:
    """Devuelve el diccionario de colores del modo (``"dark"`` | ``"light"``)."""
    if mode not in _COLORS:
        raise ValueError(f"modo debe ser uno de {MODES}, se recibió {mode!r}")
    return dict(_COLORS[mode])

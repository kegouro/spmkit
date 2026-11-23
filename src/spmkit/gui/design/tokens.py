"""Paletas semánticas y estilos de traza del espacio de análisis Fathom."""

from __future__ import annotations

#: Paletas por modo. Claves con guion_bajo para compatibilidad con string.Template.
_COLORS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1C2029",
        "surface": "#212631",
        "surface_2": "#292F3B",
        "elevated": "#333A48",
        "overlay": "rgba(6, 9, 13, 0.66)",  # modales / backdrop
        "text": "#E4E8F0",
        "text_muted": "#B2BAC9",
        "text_faint": "#959FB1",
        "border": "#353C4B",
        "border_strong": "#515B6C",
        "accent": "#AAC0FF",
        "accent_press": "#849FED",
        "accent_soft": "#2D395B",
        "on_accent": "#172541",
        "accent_2": "#E7A27D",
        "accent_2_soft": "#48352F",
        "success": "#4ADE80",
        "warning": "#FBBF24",
        "danger": "#F87171",
    },
    "light": {
        "bg": "#F2F4F8",
        "surface": "#FFFFFF",
        "surface_2": "#EBEEF3",
        "elevated": "#E1E6EF",
        "overlay": "rgba(20, 18, 12, 0.42)",
        "text": "#192335",
        "text_muted": "#4E5B6F",
        "text_faint": "#59677C",
        "border": "#D8DDE6",
        "border_strong": "#ADB7C7",
        "accent": "#364E9A",
        "accent_press": "#283E80",
        "accent_soft": "#E5EAF7",
        "on_accent": "#FFFFFF",
        "accent_2": "#984D32",
        "accent_2_soft": "#F5E7E1",
        "success": "#15803D",
        "warning": "#B45309",
        "danger": "#B91C1C",
    },
    "nanosurf": {  # grafito cálido con el oro de marca (NanoSurf/Fathom)
        "bg": "#0E0B07",
        "surface": "#16110A",
        "surface_2": "#1E1710",
        "elevated": "#29200F",
        "overlay": "rgba(13, 9, 5, 0.66)",
        "text": "#F2E9D8",
        "text_muted": "#B7A98E",
        "text_faint": "#6E5F45",
        "border": "#2A2116",
        "border_strong": "#3E3320",
        "accent": "#E8A94B",
        "accent_press": "#D2942F",
        "accent_soft": "#33280F",
        "on_accent": "#2A1E06",
        "accent_2": "#2DD4BF",
        "accent_2_soft": "#0F3A37",
        "success": "#A3BE8C",
        "warning": "#FABD2F",
        "danger": "#E86A5A",
    },
    "nord": {  # Nord — noche polar + escarcha
        "bg": "#2E3440",
        "surface": "#3B4252",
        "surface_2": "#434C5E",
        "elevated": "#4C566A",
        "overlay": "rgba(20, 25, 35, 0.60)",
        "text": "#ECEFF4",
        "text_muted": "#D8DEE9",
        "text_faint": "#7B88A1",
        "border": "#3B4252",
        "border_strong": "#4C566A",
        "accent": "#88C0D0",
        "accent_press": "#81A1C1",
        "accent_soft": "#2B3A4A",
        "on_accent": "#2E3440",
        "accent_2": "#EBCB8B",
        "accent_2_soft": "#3E3B2C",
        "success": "#A3BE8C",
        "warning": "#EBCB8B",
        "danger": "#BF616A",
    },
    "dracula": {  # Dracula — púrpura/rosa sobre noche
        "bg": "#282A36",
        "surface": "#21222C",
        "surface_2": "#343746",
        "elevated": "#44475A",
        "overlay": "rgba(15, 16, 22, 0.62)",
        "text": "#F8F8F2",
        "text_muted": "#A8AAC0",
        "text_faint": "#6272A4",
        "border": "#343746",
        "border_strong": "#44475A",
        "accent": "#BD93F9",
        "accent_press": "#A87BE0",
        "accent_soft": "#363048",
        "on_accent": "#21222C",
        "accent_2": "#FF79C6",
        "accent_2_soft": "#3A2733",
        "success": "#50FA7B",
        "warning": "#F1FA8C",
        "danger": "#FF5555",
    },
    "solarized_dark": {  # Solarized oscuro (Ethan Schoonover)
        "bg": "#002B36",
        "surface": "#073642",
        "surface_2": "#0A3D4A",
        "elevated": "#0B4553",
        "overlay": "rgba(0, 20, 26, 0.60)",
        "text": "#93A1A1",
        "text_muted": "#839496",
        "text_faint": "#586E75",
        "border": "#073642",
        "border_strong": "#0E4A5A",
        "accent": "#2AA198",
        "accent_press": "#1F8177",
        "accent_soft": "#073642",
        "on_accent": "#002B36",
        "accent_2": "#B58900",
        "accent_2_soft": "#0A3D2A",
        "success": "#859900",
        "warning": "#B58900",
        "danger": "#DC322F",
    },
    "solarized_light": {  # Solarized claro
        "bg": "#FDF6E3",
        "surface": "#FFFEF6",
        "surface_2": "#EEE8D5",
        "elevated": "#E4DCC4",
        "overlay": "rgba(40, 35, 20, 0.35)",
        "text": "#586E75",
        "text_muted": "#657B83",
        "text_faint": "#93A1A1",
        "border": "#E0D8C4",
        "border_strong": "#CFC7B0",
        "accent": "#2AA198",
        "accent_press": "#1F8177",
        "accent_soft": "#D6ECE9",
        "on_accent": "#FFFFFF",
        "accent_2": "#B58900",
        "accent_2_soft": "#F0E6C8",
        "success": "#859900",
        "warning": "#B58900",
        "danger": "#DC322F",
    },
    "gruvbox": {  # Gruvbox oscuro — retro cálido
        "bg": "#282828",
        "surface": "#32302F",
        "surface_2": "#3C3836",
        "elevated": "#504945",
        "overlay": "rgba(20, 20, 18, 0.60)",
        "text": "#EBDBB2",
        "text_muted": "#BDAE93",
        "text_faint": "#928374",
        "border": "#3C3836",
        "border_strong": "#504945",
        "accent": "#FE8019",
        "accent_press": "#D65D0E",
        "accent_soft": "#3D2E1F",
        "on_accent": "#282828",
        "accent_2": "#83A598",
        "accent_2_soft": "#26343A",
        "success": "#B8BB26",
        "warning": "#FABD2F",
        "danger": "#FB4934",
    },
}

#: Temas disponibles (clave, etiqueta), en orden para el selector de apariencia.
THEMES: tuple[tuple[str, str], ...] = (
    ("dark", "Carbono (oscuro)"),
    ("light", "Porcelana (claro)"),
    ("nanosurf", "NanoSurf oro"),
    ("nord", "Nord"),
    ("dracula", "Dracula"),
    ("solarized_dark", "Solarized oscuro"),
    ("solarized_light", "Solarized claro"),
    ("gruvbox", "Gruvbox"),
)

#: Tintas científicas para las ramas crudas, el modelo y las referencias.
TRACES = {
    "extend": "#D5DCE9",
    "retract": "#E6AC93",
    "fit": "#AAC0FF",
    "contact": "#E7A27D",
    "residual": "#738198",
}

LIGHT_TRACES = {
    "extend": "#24344A",
    "retract": "#A25639",
    "fit": "#405DB3",
    "contact": "#984D32",
    "residual": "#697993",
}

CATEGORICAL: tuple[str, ...] = ("#506BBC", "#AB634A", "#638475", "#896BA0")

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


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.lstrip("#")
    return tuple(int(v[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _luminance(value: str) -> float:
    r, g, b = _hex_to_rgb(value)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_dark(mode: str) -> bool:
    """``True`` si el tema es oscuro (por la luminancia de su fondo)."""
    return _luminance(_COLORS.get(mode, _COLORS["dark"])["bg"]) < 0.4


def _accent_shades(accent: str, dark: bool) -> dict[str, str]:
    """Deriva ``accent_press``/``accent_soft``/``on_accent`` de un acento base."""
    import colorsys

    r, g, b = _hex_to_rgb(accent)
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    press = colorsys.hls_to_rgb(h, max(0.0, lum * 0.82), s)  # pulsado: más oscuro
    if dark:
        soft = colorsys.hls_to_rgb(h, lum * 0.22, min(s, 0.55))  # tinte oscuro
    else:
        soft = colorsys.hls_to_rgb(h, 1.0 - (1.0 - lum) * 0.22, min(s, 0.6))  # tinte claro
    on = "#0A0A0A" if _luminance(accent) > 0.55 else "#FFFFFF"  # texto legible sobre el acento
    return {
        "accent": accent,
        "accent_press": _rgb_to_hex(press),
        "accent_soft": _rgb_to_hex(soft),
        "on_accent": on,
    }


def colors(mode: str = "dark", accent: str | None = None) -> dict[str, str]:
    """Paleta del tema ``mode``; si se pasa ``accent`` (hex) sustituye el color de acento.

    El acento personalizado deriva sus variantes (pulsado/suave/texto) automáticamente.
    """
    if mode not in _COLORS:
        raise ValueError(f"tema desconocido: {mode!r} (usa uno de {[k for k, _ in THEMES]})")
    palette = dict(_COLORS[mode])
    if accent:
        palette.update(_accent_shades(accent, is_dark(mode)))
    return palette

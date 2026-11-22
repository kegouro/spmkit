"""Apariencia de la app — tema + acento + tamaño de fuente, con persistencia.

Modelo serializable que junta las tres perillas de personalización visual y las aplica a
la ``QApplication`` vía :mod:`spmkit.gui.design.theme`. Se guarda/lee de ``QSettings`` para
que la elección del usuario sobreviva entre sesiones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from spmkit.gui.design import theme, tokens

#: Escalas tipográficas ofrecidas (etiqueta, px de la fuente base).
FONT_SCALES: tuple[tuple[str, int], ...] = (
    ("Compacto", 12),
    ("Normal", 13),
    ("Cómodo", 14),
    ("Grande", 16),
)


# Each pair contains inks for a light and a dark chart background, respectively.
TRACE_PALETTES: dict[str, tuple[str, dict[str, str], dict[str, str]]] = {
    "instrument": ("Instrumento", tokens.LIGHT_TRACES, tokens.TRACES),
    "ocean": (
        "Océano",
        {"extend": "#194B67", "retract": "#16765A", "fit": "#8247A5"},
        {"extend": "#B2DFF0", "retract": "#65D4AA", "fit": "#D0A7EE"},
    ),
    "oxide": (
        "Óxido",
        {"extend": "#613828", "retract": "#775B09", "fit": "#335A83"},
        {"extend": "#F4C8AE", "retract": "#E5BC64", "fit": "#92C0ED"},
    ),
}


def _lum(color: str) -> float:
    rgb = tokens._hex_to_rgb(color)
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def _legible(color: str, bg_lum: float, minimum: float) -> str:
    end = 0 if bg_lum > 0.179 else 1
    rgb = tokens._hex_to_rgb(color)
    for step in range(11):
        candidate = "#" + "".join(f"{round(255 * (v + (end - v) * step / 10)):02X}" for v in rgb)
        lum = _lum(candidate)
        if (max(lum, bg_lum) + 0.05) / (min(lum, bg_lum) + 0.05) >= minimum:
            return candidate
    return candidate


@dataclass(frozen=True)
class Appearance:
    """Preferencias visuales: tema, acento opcional (hex) y tamaño de fuente base."""

    theme: str = "dark"
    accent: str | None = None  # ``None`` = usa el acento del tema
    font_px: int = 13

    trace_palette: str = "instrument"
    plot_background: str | None = None

    def chart_colors(self) -> tuple[str, str, dict[str, str]]:
        bg = self.plot_background or tokens.colors(self.theme)["surface"]
        luminance = _lum(bg)
        dark = luminance <= 0.179
        inks = dict(tokens.TRACES if dark else tokens.LIGHT_TRACES)
        _, light_ink, dark_ink = TRACE_PALETTES[self.trace_palette]
        inks.update(dark_ink if dark else light_ink)
        fg = _legible("#B2BAC9" if dark else "#4E5B6F", luminance, 4.5)
        return bg, fg, {role: _legible(color, luminance, 3) for role, color in inks.items()}

    def normalized(self) -> Appearance:
        """Corrige valores fuera de rango (tema desconocido → 'dark')."""
        theme_key = self.theme if self.theme in dict(tokens.THEMES) else "dark"
        font = int(self.font_px) if 10 <= int(self.font_px) <= 22 else 13
        accent = self.accent if (self.accent and self.accent.startswith("#")) else None
        palette = self.trace_palette if self.trace_palette in TRACE_PALETTES else "instrument"
        bg = self.plot_background
        return Appearance(
            theme_key,
            accent,
            font,
            palette,
            bg if bg and re.fullmatch(r"#[0-9a-fA-F]{6}", bg) else None,
        )


def apply_appearance(app: Any, appearance: Appearance) -> None:
    """Aplica la apariencia (tema + acento + fuente) a la ``QApplication``."""
    a = appearance.normalized()
    theme.apply(app, a.theme, a.accent, a.font_px)


def load_appearance(settings: Any, default_mode: str = "light") -> Appearance:
    """Lee la apariencia de ``QSettings`` (tolerante a ausencias)."""
    theme_key = str(settings.value("theme", default_mode) or default_mode)
    accent = settings.value("accent", "") or ""
    accent_val = str(accent) if str(accent).startswith("#") else None
    try:
        font_px = int(settings.value("font_px", 13) or 13)
    except (TypeError, ValueError):
        font_px = 13
    return Appearance(
        theme_key,
        accent_val,
        font_px,
        str(settings.value("trace_palette", "instrument")),
        str(settings.value("plot_background", "") or "") or None,
    ).normalized()


def save_appearance(settings: Any, appearance: Appearance) -> None:
    """Guarda la apariencia en ``QSettings``."""
    a = appearance.normalized()
    settings.setValue("theme", a.theme)
    settings.setValue("accent", a.accent or "")
    settings.setValue("font_px", a.font_px)
    settings.setValue("trace_palette", a.trace_palette)
    settings.setValue("plot_background", a.plot_background or "")

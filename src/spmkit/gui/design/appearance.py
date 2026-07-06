"""Apariencia de la app — tema + acento + tamaño de fuente, con persistencia.

Modelo serializable que junta las tres perillas de personalización visual y las aplica a
la ``QApplication`` vía :mod:`spmkit.gui.design.theme`. Se guarda/lee de ``QSettings`` para
que la elección del usuario sobreviva entre sesiones.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class Appearance:
    """Preferencias visuales: tema, acento opcional (hex) y tamaño de fuente base."""

    theme: str = "dark"
    accent: str | None = None  # ``None`` = usa el acento del tema
    font_px: int = 13

    def normalized(self) -> Appearance:
        """Corrige valores fuera de rango (tema desconocido → 'dark')."""
        theme_key = self.theme if self.theme in dict(tokens.THEMES) else "dark"
        font = int(self.font_px) if 10 <= int(self.font_px) <= 22 else 13
        accent = self.accent if (self.accent and self.accent.startswith("#")) else None
        return Appearance(theme=theme_key, accent=accent, font_px=font)


def apply_appearance(app: Any, appearance: Appearance) -> None:
    """Aplica la apariencia (tema + acento + fuente) a la ``QApplication``."""
    a = appearance.normalized()
    theme.apply(app, a.theme, a.accent, a.font_px)


def load_appearance(settings: Any) -> Appearance:
    """Lee la apariencia de ``QSettings`` (tolerante a ausencias)."""
    theme_key = str(settings.value("theme", "dark") or "dark")
    accent = settings.value("accent", "") or ""
    accent_val = str(accent) if str(accent).startswith("#") else None
    try:
        font_px = int(settings.value("font_px", 13) or 13)
    except (TypeError, ValueError):
        font_px = 13
    return Appearance(theme=theme_key, accent=accent_val, font_px=font_px).normalized()


def save_appearance(settings: Any, appearance: Appearance) -> None:
    """Guarda la apariencia en ``QSettings``."""
    a = appearance.normalized()
    settings.setValue("theme", a.theme)
    settings.setValue("accent", a.accent or "")
    settings.setValue("font_px", a.font_px)

"""Tests de personalización de apariencia (F4): temas/presets, acento, fuente, diálogo."""

from __future__ import annotations

from spmkit.gui.design import theme, tokens
from spmkit.gui.design.appearance import (
    Appearance,
    load_appearance,
    save_appearance,
)

# Claves que el QSS necesita de toda paleta (si falta una, build_qss lanza KeyError).
_REQUIRED = {
    "bg",
    "surface",
    "surface_2",
    "elevated",
    "text",
    "text_muted",
    "text_faint",
    "border",
    "border_strong",
    "accent",
    "accent_press",
    "accent_soft",
    "on_accent",
    "accent_2",
    "accent_2_soft",
}


class _FakeSettings:
    def __init__(self) -> None:
        self._d: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self._d.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self._d[key] = value


def test_every_theme_is_complete_and_builds_qss() -> None:
    for key, _label in tokens.THEMES:
        palette = tokens.colors(key)
        assert set(palette) >= _REQUIRED, f"{key} incompleto"
        qss = theme.build_qss(key)
        assert "$" not in qss and palette["accent"] in qss  # sin tokens sin sustituir


def test_custom_accent_overrides_and_derives() -> None:
    base = tokens.colors("dark")
    custom = tokens.colors("dark", accent="#FF00AA")
    assert custom["accent"] == "#FF00AA" and custom["accent"] != base["accent"]
    # deriva pulsado/suave/texto distintos del acento base
    assert custom["accent_press"] != "#FF00AA"
    assert custom["on_accent"] in ("#0A0A0A", "#FFFFFF")


def test_font_scale_threads_into_qss() -> None:
    assert "font-size: 16px" in theme.build_qss("dark", font_px=16)
    assert "font-size: 12px" in theme.build_qss("light", font_px=12)


def test_is_dark_classifies_presets() -> None:
    assert tokens.is_dark("dark") and tokens.is_dark("nord") and tokens.is_dark("gruvbox")
    assert not tokens.is_dark("light") and not tokens.is_dark("solarized_light")


def test_appearance_normalizes_bad_values() -> None:
    a = Appearance(theme="inexistente", accent="rojo", font_px=999).normalized()
    assert a.theme == "dark" and a.accent is None and a.font_px == 13


def test_appearance_settings_roundtrip() -> None:
    s = _FakeSettings()
    save_appearance(s, Appearance(theme="nord", accent="#88C0D0", font_px=14))
    loaded = load_appearance(s)
    assert loaded.theme == "nord" and loaded.accent == "#88C0D0" and loaded.font_px == 14


def test_appearance_dialog_picks_theme(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.widgets import AppearanceDialog

    dialog = AppearanceDialog(Appearance(theme="dark"))
    qtbot.addWidget(dialog)
    seen: list[object] = []
    dialog.changed.connect(seen.append)
    dialog._pick_theme("dracula")
    assert dialog.appearance().theme == "dracula"
    assert seen and getattr(seen[-1], "theme", None) == "dracula"


def test_workspace_set_appearance(qtbot) -> None:  # type: ignore[no-untyped-def]
    from spmkit.gui.shell.workspace import Workspace

    ws = Workspace()
    qtbot.addWidget(ws)
    ws.set_appearance(Appearance(theme="gruvbox", accent="#FE8019", font_px=15))
    assert ws.mode == "gruvbox"
    assert ws.appearance.accent == "#FE8019"
    ws.toggle_theme()  # gruvbox no es dark base → va a dark; solo cambia el tema
    assert ws.appearance.font_px == 15  # preserva fuente/acento al alternar

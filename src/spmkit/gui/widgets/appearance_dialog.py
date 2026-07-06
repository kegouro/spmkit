"""Diálogo de apariencia — elige tema, acento y tamaño de fuente, con vista previa en vivo.

Muestra los temas como **tarjetas** pintadas con sus propios colores (se ven antes de
elegir), un selector de acento opcional y la escala tipográfica. Emite ``changed`` en cada
ajuste para que el workspace aplique la apariencia en vivo; ``Cancelar`` revierte.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from spmkit.gui.design import tokens
from spmkit.gui.design.appearance import FONT_SCALES, Appearance
from spmkit.gui.widgets.annotation_dialog import ColorButton


class _ThemeCard(QFrame):
    """Tarjeta que previsualiza un tema pintándose con sus propios colores."""

    clicked = pyqtSignal(str)

    def __init__(self, key: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._selected = False
        c = tokens.colors(key)
        self.setFixedSize(150, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        # Franja tipo barra de herramientas (surface_2) con un "botón" de acento.
        bar = QLabel()
        bar.setFixedHeight(16)
        bar.setStyleSheet(
            f"background:{c['surface_2']}; border-radius:4px; "
            f"border-left:22px solid {c['accent']};"
        )
        lay.addWidget(bar)
        # Muestras de color (acento, acento 2, texto).
        chips = QHBoxLayout()
        chips.setSpacing(5)
        for col in (c["accent"], c["accent_2"], c["text_muted"]):
            chip = QLabel()
            chip.setFixedSize(20, 12)
            chip.setStyleSheet(f"background:{col}; border-radius:3px;")
            chips.addWidget(chip)
        chips.addStretch(1)
        lay.addLayout(chips)
        lay.addStretch(1)
        name = QLabel(label)
        name.setStyleSheet(f"color:{c['text']}; font-weight:500; background:transparent;")
        lay.addWidget(name)

        self._c = c
        self._paint()

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - override Qt
        self.clicked.emit(self._key)

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self._paint()

    def _paint(self) -> None:
        c = self._c
        edge = c["accent"] if self._selected else c["border_strong"]
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"_ThemeCard {{ background:{c['bg']}; "
            f"border:{width}px solid {edge}; border-radius:10px; }}"
        )


class AppearanceDialog(QDialog):
    """Editor de apariencia con vista previa en vivo."""

    changed = pyqtSignal(object)  # Appearance (para aplicar en vivo)

    def __init__(self, current: Appearance, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apariencia")
        self._theme = current.theme
        self._accent = current.accent
        self._cards: dict[str, _ThemeCard] = {}

        root = QVBoxLayout(self)
        title = QLabel("Tema")
        title.setProperty("role", "title")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (key, label) in enumerate(tokens.THEMES):
            card = _ThemeCard(key, label)
            card.clicked.connect(self._pick_theme)
            self._cards[key] = card
            grid.addWidget(card, i // 4, i % 4)
        root.addLayout(grid)

        # --- acento ---
        accent_row = QHBoxLayout()
        self._accent_chk = QCheckBox("Acento personalizado")
        self._accent_chk.setChecked(current.accent is not None)
        self._accent_chk.toggled.connect(self._on_accent_toggle)
        self._accent_btn = ColorButton(current.accent or tokens.colors(current.theme)["accent"])
        self._accent_btn.clicked.connect(self._emit)  # el picker ya cambió el color
        accent_row.addWidget(self._accent_chk)
        accent_row.addWidget(self._accent_btn)
        accent_row.addStretch(1)
        root.addLayout(accent_row)

        # --- fuente ---
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Tamaño de fuente:"))
        self._font = QComboBox()
        for name, px in FONT_SCALES:
            self._font.addItem(f"{name} ({px}px)", px)
        idx = self._font.findData(current.font_px)
        self._font.setCurrentIndex(idx if idx >= 0 else 1)
        self._font.currentIndexChanged.connect(lambda _i: self._emit())
        font_row.addWidget(self._font)
        font_row.addStretch(1)
        root.addLayout(font_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._accent_btn.setEnabled(current.accent is not None)
        self._sync_cards()

    # ---- interacción ----
    def _pick_theme(self, key: str) -> None:
        self._theme = key
        if not self._accent_chk.isChecked():  # el botón muestra el acento del tema
            self._accent_btn.set_color(tokens.colors(key)["accent"])
        self._sync_cards()
        self._emit()

    def _on_accent_toggle(self, on: bool) -> None:
        self._accent_btn.setEnabled(on)
        if not on:
            self._accent_btn.set_color(tokens.colors(self._theme)["accent"])
        self._emit()

    def _sync_cards(self) -> None:
        for key, card in self._cards.items():
            card.set_selected(key == self._theme)

    def _emit(self) -> None:
        self.changed.emit(self.appearance())

    def appearance(self) -> Appearance:
        accent = self._accent_btn.color() if self._accent_chk.isChecked() else None
        return Appearance(theme=self._theme, accent=accent, font_px=int(self._font.currentData()))

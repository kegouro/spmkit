"""Personalización de trazas y ejes del visor de fuerza."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

_PATTERNS = {
    "Continua": Qt.PenStyle.SolidLine,
    "Guiones": Qt.PenStyle.DashLine,
    "Puntos": Qt.PenStyle.DotLine,
    "Guion y punto": Qt.PenStyle.DashDotLine,
}


@dataclass(frozen=True)
class CurveStyle:
    strokes: tuple[tuple[float, str], ...] = (
        (1.6, "Continua"),
        (1.4, "Guiones"),
        (2.2, "Continua"),
    )
    axis_width: float = 1.0
    font_px: int = 13

    @classmethod
    def from_preference(cls, value: str) -> CurveStyle:
        try:
            data = json.loads(value)
            strokes = tuple((float(w), name) for w, name in data["strokes"])
            axis, size = float(data["axis_width"]), int(data["font_px"])
            if (
                len(strokes) == 3
                and all(0.5 <= width <= 8 and name in _PATTERNS for width, name in strokes)
                and 0.5 <= axis <= 8
                and 9 <= size <= 32
            ):
                return cls(strokes, axis, size)
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
        return cls()

    def preference(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def pens(self) -> Iterator[dict[str, Any]]:
        for width, name in self.strokes:
            yield {"width": width, "style": _PATTERNS[name]}


class CurveStyleDialog(QDialog):
    def __init__(self, style: CurveStyle, titles: tuple[str, str], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Estilo de la curva")
        layout = QFormLayout(self)
        self.strokes = []
        for name in ("Aproximación", "Retracción", "Ajuste"):
            row = QHBoxLayout()
            width = self.width_field()
            pattern = QComboBox()
            pattern.addItems(_PATTERNS.keys())
            width.setAccessibleName(f"Grosor · {name}")
            pattern.setAccessibleName(f"Patrón · {name}")
            row.addWidget(width)
            row.addWidget(pattern)
            layout.addRow(name, row)
            self.strokes.append((width, pattern))
        self.axes = self.width_field()
        layout.addRow("Grosor de ejes", self.axes)
        self.font_size = QSpinBox()
        self.font_size.setRange(9, 32)
        self.font_size.setSuffix(" px")
        layout.addRow("Texto de ejes", self.font_size)
        self.names = []
        for axis, current in zip(("X", "Y"), titles, strict=True):
            edit = QLineEdit()
            edit.setPlaceholderText(current)
            edit.setMaxLength(90)
            self.names.append(edit)
            layout.addRow(f"Nombre del eje {axis}", edit)
        self.set_style(style)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.reset)
        layout.addRow(buttons)

    @staticmethod
    def width_field() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(0.5, 8)
        field.setSingleStep(0.5)
        field.setSuffix(" px")
        return field

    def reset(self) -> None:
        self.set_style(CurveStyle())
        for edit in self.names:
            edit.clear()

    def set_style(self, style: CurveStyle) -> None:
        for (width, pattern), (size, name) in zip(self.strokes, style.strokes, strict=True):
            width.setValue(size)
            pattern.setCurrentText(name)
        self.axes.setValue(style.axis_width)
        self.font_size.setValue(style.font_px)

    def style_value(self) -> CurveStyle:
        return CurveStyle(
            tuple((w.value(), p.currentText()) for w, p in self.strokes),
            self.axes.value(),
            self.font_size.value(),
        )

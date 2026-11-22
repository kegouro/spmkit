"""Guía reutilizable anclada a los controles visibles de Fathom."""

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class WorkspaceGuide(QFrame):
    def __init__(self, workspace: QWidget) -> None:
        super().__init__(workspace)
        self.setObjectName("workspaceGuide")
        self._workspace = workspace
        self._outline = QFrame(workspace)
        self._outline.setObjectName("guideTarget")
        self._outline.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._outline.hide()
        self._steps: list[tuple[QWidget, str, str]] = []
        self._index = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self._progress = QLabel()
        self._progress.setProperty("role", "muted")
        self._title = QLabel()
        self._title.setProperty("role", "title")
        self._body = QLabel()
        self._body.setWordWrap(True)
        for label in (self._progress, self._title, self._body):
            layout.addWidget(label)
        row = QHBoxLayout()
        close = QPushButton("Cerrar")
        close.clicked.connect(self.dismiss)
        self._back = QPushButton("Atrás")
        self._back.clicked.connect(lambda: self._select(self._index - 1))
        self._next = QPushButton()
        self._next.setProperty("primary", True)
        self._next.clicked.connect(self.advance)
        row.addWidget(close)
        row.addStretch()
        row.addWidget(self._back)
        row.addWidget(self._next)
        layout.addLayout(row)
        workspace.installEventFilter(self)
        self.hide()

    def start(self, steps: list[tuple[QWidget, str, str]]) -> None:
        self._steps = [step for step in steps if step[0].isVisible()]
        if self._steps:
            self.show()
            self._select(0)
            self._next.setFocus()

    def _select(self, index: int) -> None:
        self._index = index
        _, title, body = self._steps[index]
        self._progress.setText(f"Guía de Fathom  ·  {index + 1} de {len(self._steps)}")
        self._title.setText(title)
        self._body.setText(body)
        self.setAccessibleName(title)
        self.setAccessibleDescription(body)
        self._back.setEnabled(index > 0)
        self._next.setText("Terminar" if index == len(self._steps) - 1 else "Siguiente")
        self._next.setAccessibleDescription(f"{title}. {body}")
        self._place()

    def _place(self) -> None:
        target = self._steps[self._index][0]
        if not target.isVisible():
            self.dismiss()
            return
        area = QRect(target.mapTo(self._workspace, QPoint()), target.size())
        self._outline.setGeometry(area)
        self._outline.show()
        self._outline.raise_()
        self.setFixedWidth(min(364, self._workspace.width() - 16))
        self.adjustSize()
        x = min(area.left(), self._workspace.width() - self.width() - 8)
        y = area.bottom() + 6
        if y + self.height() > self._workspace.height():
            y = area.top() - self.height() - 6
        self.move(max(8, x), max(8, y))
        self.raise_()

    def advance(self) -> None:
        if self._index + 1 < len(self._steps):
            self._select(self._index + 1)
        else:
            self.dismiss()

    def dismiss(self) -> None:
        self.hide()
        self._outline.hide()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802
        if (
            event
            and event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest)
            and self.isVisible()
        ):
            self._place()
        return super().eventFilter(obj, event)

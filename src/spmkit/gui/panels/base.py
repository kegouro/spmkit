"""Panel base — todo panel del workspace hereda de aquí.

Aporta el **sandbox de errores**: si ``build()`` o ``refresh()`` lanzan (típico en
paneles-plugin de terceros), el panel muestra un *Error Card* con el mensaje y un
traceback plegable, en vez de tumbar toda la app — como VS Code con extensiones rotas.
"""

from __future__ import annotations

import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Panel(QWidget):
    """Widget base de un panel del workspace, con render aislado (sandbox).

    Las subclases sobrescriben :meth:`build` (una vez) y opcionalmente
    :meth:`refresh` (al cambiar datos). Ambos corren envueltos en un try/except; una
    excepción se convierte en un *Error Card* dentro del panel, recuperable.
    """

    #: Título mostrado en la barra del dock.
    title: str = "Panel"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._content: QWidget | None = None
        self._errored = False
        self._mount(self.build)

    # ---- API que sobrescriben las subclases ----
    def build(self) -> QWidget:
        """Construye y devuelve el widget de contenido del panel."""
        placeholder = QLabel(self.title)
        placeholder.setProperty("role", "muted")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return placeholder

    def refresh(self) -> None:
        """Actualiza el panel ante nuevos datos (opcional)."""

    # ---- sandbox ----
    @property
    def errored(self) -> bool:
        """``True`` si el panel está mostrando un Error Card."""
        return self._errored

    def refresh_safe(self) -> None:
        """Corre :meth:`refresh` de forma aislada (usarlo desde el shell)."""
        try:
            self.refresh()
        except Exception as exc:  # noqa: BLE001 - aislado, se muestra al usuario
            self._show_error(exc)

    def rebuild(self) -> None:
        """Reintenta construir el panel (botón 'Reiniciar panel')."""
        self._mount(self.build)

    def _mount(self, factory: object) -> None:
        self._clear()
        try:
            content = factory()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 - un panel roto no tumba la app
            self._show_error(exc)
            return
        self._errored = False
        self._content = content
        if content is not None:
            self._root.addWidget(content)

    def _show_error(self, exc: Exception) -> None:
        self._clear()
        self._errored = True
        card = QWidget()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        title = QLabel(f"El panel «{self.title}» falló")
        title.setProperty("role", "title")
        msg = QLabel(str(exc) or exc.__class__.__name__)
        msg.setProperty("role", "muted")
        msg.setWordWrap(True)
        tb = QLabel("".join(traceback.format_exception_only(type(exc), exc)).strip())
        tb.setProperty("role", "readout")
        tb.setWordWrap(True)
        retry = QPushButton("Reiniciar panel")
        retry.clicked.connect(self.rebuild)
        for w in (title, msg, tb, retry):
            lay.addWidget(w)
        lay.addStretch(1)
        self._content = card
        self._root.addWidget(card)

    def _clear(self) -> None:
        if self._content is not None:
            self._content.setParent(None)
            self._content.deleteLater()
            self._content = None

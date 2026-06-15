"""Diálogo de bienvenida con una explicación breve de spmkit."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from spmkit import __version__

_HTML = f"""
<h2 style="margin-bottom:2px;">spmkit <span style="font-weight:400;">v{__version__}</span></h2>
<p style="color:#8B949E; margin-top:0;">Analizador open-source de AFM/KPFM · SPM Lab UTFSM</p>
<p>Abre un archivo <b>.nid</b>, <b>.nhf</b> o <b>.gwy</b> (botón <b>Abrir</b> o
arrastrándolo a la ventana) y trabaja en las pestañas:</p>
<ul>
  <li><b>Visor</b> — imagen, perfil de línea interactivo y rugosidad (ISO 25178) / KPFM.</li>
  <li><b>Nanomecánica</b> — curvas fuerza-distancia, ajuste de Hertz y mapas de
      módulo/adhesión.</li>
  <li><b>Resonancia</b> — sensado de masa por evaporación: f(t), masa y tasa
      desde espectros de thermal tuning.</li>
  <li><b>Editor de figuras</b> — figuras de publicación con colormaps científicos,
      barra de escala y textos arrastrables (doble-clic para editar).</li>
  <li><b>Comparar</b> — fusiona 2–4 archivos en un panel con escala y color compartidos.</li>
</ul>
<p style="color:#8B949E;">Atajos: <b>Ctrl+O</b> abrir · <b>Ctrl+R</b> reporte ·
<b>Ctrl+1…4</b> pestañas · <b>Ctrl+D</b> tema claro/oscuro.</p>
"""


class WelcomeDialog(QtWidgets.QDialog):
    """Diálogo informativo, mostrable solo en el primer arranque."""

    SETTINGS_KEY = "show_welcome"

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bienvenido a spmkit")
        self.setMinimumWidth(520)
        layout = QtWidgets.QVBoxLayout(self)

        body = QtWidgets.QLabel(_HTML)
        body.setWordWrap(True)
        body.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(body)

        self.dont_show = QtWidgets.QCheckBox("No volver a mostrar al iniciar")
        layout.addWidget(self.dont_show)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if btn is not None:
            btn.setText("Empezar")
            btn.setProperty("primary", True)
        layout.addWidget(buttons)

    @classmethod
    def maybe_show(cls, parent: QtWidgets.QWidget, settings: QtCore.QSettings) -> None:
        """Muestra el diálogo salvo que el usuario lo haya desactivado."""
        if not settings.value(cls.SETTINGS_KEY, True, type=bool):
            return
        dlg = cls(parent)
        dlg.exec()
        if dlg.dont_show.isChecked():
            settings.setValue(cls.SETTINGS_KEY, False)

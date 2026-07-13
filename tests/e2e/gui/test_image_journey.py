from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtWidgets import QFileDialog, QPushButton

from spmkit.gui.app_workspace import build_workspace


def test_corrupt_gwy_via_open_action_keeps_gui_alive(
    qtbot, monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    corrupt_path = tmp_path / "corrupt_image.gwy"
    corrupt_path.write_bytes(b"not a Gwyddion file")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(corrupt_path), "")),
    )
    ws = build_workspace()
    ws.show()
    qtbot.wait(0)

    try:
        open_action = next(
            action for action in ws._persp_bar.actions() if "Abrir" in action.text()
        )
        open_action.trigger()
        qtbot.wait(0)

        canvas = ws.panel("image_canvas")
        assert canvas is not None
        assert not ws.isHidden()
        assert ws.active_perspective != "image"
        assert canvas._vm.data is None
        assert ws._status._message.text() == (
            "No se pudo abrir corrupt_image.gwy: "
            "archivo .gwy inválido o corrupto: corrupt_image.gwy"
        )
    finally:
        ws.close()
        ws.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        qtbot.wait(0)


def test_real_gwy_gui_image_journey(
    qtbot, monkeypatch, real_gwy_path: Path, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(real_gwy_path), "")),
    )
    ws = build_workspace()
    ws.show()
    qtbot.wait(0)

    try:
        open_action = next(
            action for action in ws._persp_bar.actions() if "Abrir" in action.text()
        )
        open_action.trigger()
        qtbot.wait(0)

        assert ws.active_perspective == "image"
        status = ws._status._message.text()
        assert real_gwy_path.name in status
        assert "imagen" in status
        assert "3 canales" in status

        canvas = ws.panel("image_canvas")
        analysis = ws.panel("image_analysis")
        assert canvas is not None and analysis is not None
        image_vm = canvas._vm
        assert image_vm.data is not None
        assert len(image_vm.data.channels) == 3
        assert image_vm.names == ["Z-Axis", "Z-Axis", "CPD"]

        selector = canvas._channel
        assert selector.count() == 3
        forward_label = selector.itemText(0)
        backward_label = selector.itemText(1)
        assert forward_label != backward_label
        assert "Z-Axis" in forward_label and "Z-Axis" in backward_label

        forward = image_vm.raw_channel_at(0)
        backward = image_vm.raw_channel_at(1)
        assert forward is not None and backward is not None
        assert forward.direction == "forward"
        assert backward.direction == "backward"
        forward_raw = np.asarray(forward.data).copy()
        backward_raw = np.asarray(backward.data).copy()
        assert not np.array_equal(forward_raw, backward_raw)

        selector.setCurrentIndex(0)
        assert image_vm.current_index == 0
        selector.setCurrentIndex(1)
        assert image_vm.current_index == 1
        assert image_vm.raw_channel_at(1) is backward
        np.testing.assert_array_equal(image_vm.raw_channel_at(0).data, forward_raw)
        np.testing.assert_array_equal(image_vm.raw_channel_at(1).data, backward_raw)

        selector.setCurrentIndex(0)
        profile = image_vm.profile((0.5, 0.5), (5.5, 3.5))
        assert profile is not None
        assert image_vm.last_profile is profile
        assert analysis._plot.listDataItems()

        profile_path = tmp_path / "profile.csv"
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (str(profile_path), "")),
        )
        profile_button = next(
            button
            for button in analysis.findChildren(QPushButton)
            if "Exportar perfil" in button.text()
        )
        qtbot.mouseClick(profile_button, Qt.MouseButton.LeftButton)
        assert profile_path.is_file()
        with profile_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        assert reader.fieldnames == ["distance[m]", "height[m]"]
        assert len(rows) == len(profile)
        np.testing.assert_allclose(
            [float(row["distance[m]"]) for row in rows], profile.distance
        )
        np.testing.assert_allclose([float(row["height[m]"]) for row in rows], profile.height)

        selector.setCurrentIndex(2)
        assert image_vm.current_index == 2
        assert image_vm.channel == "CPD"
        assert analysis._wf.isVisible()
        analysis._wf.setValue(4.5)
        assert image_vm.tip_work_function == 4.5
        readout = analysis._readout.text()
        assert "KPFM (CPD)" in readout
        assert "Φ muestra" in readout

        figure_action = next(
            action for action in ws._persp_bar.actions() if action.text() == "Figura"
        )
        figure_action.trigger()
        qtbot.wait(0)
        assert ws.active_perspective == "figure"

        figure = ws.panel("figure_editor")
        assert figure is not None
        assert figure._vm.channel == "Z-Axis"
        assert "Z-Axis" in figure._channel.currentText()
        assert figure._cmap.currentText() == "gold"
        assert figure._vm.spec.colormap == "gold"

        figure_path = tmp_path / "figure.png"
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (str(figure_path), "")),
        )
        figure_button = next(
            button
            for button in figure.findChildren(QPushButton)
            if button.text() == "Exportar figura…"
        )
        qtbot.mouseClick(figure_button, Qt.MouseButton.LeftButton)
        figure_bytes = figure_path.read_bytes()
        assert figure_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(figure_bytes) > 1_000
    finally:
        ws.close()
        ws.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        qtbot.wait(0)

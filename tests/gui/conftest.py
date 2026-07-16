"""Fixtures compartidas de los tests de GUI (curvas sintéticas para la VM/paneles).

Si el entorno no tiene el stack de GUI (PyQt6 + pytest-qt) —como el CI, que instala sin
el extra ``gui``— se omite toda la carpeta ``tests/gui`` en la colección, en vez de
fallar al importar. Local, con el extra ``gui``, los tests se corren normalmente.
"""

from __future__ import annotations

import gc

import numpy as np
import pytest

from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume

try:
    import PyQt6  # noqa: F401
    import pytestqt  # noqa: F401

    _HAS_GUI = True
except ImportError:  # pragma: no cover - CI sin extra gui
    _HAS_GUI = False

#: Sin el stack de GUI, pytest ignora los ``test_*.py`` de esta carpeta.
collect_ignore_glob = [] if _HAS_GUI else ["test_*.py"]


if _HAS_GUI:

    @pytest.fixture(autouse=True)
    def _flush_qt():  # type: ignore[no-untyped-def]
        """Flush deferred Qt deletions safely between GUI tests."""
        yield

        import gc

        import pyqtgraph as pg
        from PyQt6.QtCore import QCoreApplication, QEvent

        app = QCoreApplication.instance()
        if app is None:
            return

        # Keep active ViewBox wrappers alive while Qt processes native deletion.
        held_viewboxes = list(pg.ViewBox.AllViews.keys())

        gc.collect()
        QCoreApplication.sendPostedEvents(
            None,
            QEvent.Type.DeferredDelete,
        )

        gc.collect()
        QCoreApplication.sendPostedEvents(
            None,
            QEvent.Type.DeferredDelete,
        )

        # References are released naturally when the fixture finalizer returns.


def _hertz_curve(
    young: float = 1.0e6, radius: float = 10e-9, sep_contact: float = 3e-7
) -> ForceCurve:
    """Curva de fuerza sintética ya calibrada (Hertz esférico, módulo conocido)."""
    separation = np.linspace(6e-7, 0.0, 400)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(sep_contact - separation, 0.0, None)
    force = k * delta**1.5
    zeros = np.zeros_like(separation)
    extend = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=separation,
        raw_deflection=zeros,
        deflection=zeros,
        force=force,
        separation=separation,
        state="force_n",
    )
    retract = ForceSegment(
        segment_type="retract",
        direction="retract",
        raw_height=separation,
        raw_deflection=zeros,
        deflection=zeros,
        force=force,
        separation=separation,
        state="force_n",
    )
    return ForceCurve(segments=(extend, retract))


@pytest.fixture
def synthetic_volume():
    """Factoría de un force-volume sintético de ``n`` curvas con módulo creciente."""

    def _make(n: int = 3) -> ForceVolume:
        curves = tuple(_hertz_curve(young=1.0e6 * (1 + 0.1 * i)) for i in range(n))
        return ForceVolume.from_curves(curves, grid_shape=(1, n), x_range=1e-6, y_range=1e-6)

    return _make

"""Render de figuras de publicación: 2D como imagen, 1D/espectral como línea."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from spmkit.core.models import SPMChannel  # noqa: E402
from spmkit.core.viz.figure import render_channel  # noqa: E402


def test_render_2d_channel_is_image() -> None:
    ch = SPMChannel(name="Z", data=np.random.rand(16, 16), unit="m", x_range=1e-6, y_range=1e-6)
    fig = render_channel(ch)
    ax = fig.axes[0]
    assert ax.images and not ax.lines  # imshow, no línea


def test_render_1d_spectral_channel_is_line_no_warning() -> None:
    """Un canal 1×N (espectro) se dibuja como línea, sin el imshow degenerado (ylims singulares)."""
    n = 200
    psd = np.abs(np.sin(np.linspace(0, 6, n))) + 0.01
    ch = SPMChannel(
        name="Amplitude Spectral Density",
        data=psd.reshape(1, n),
        unit="m/√Hz",
        x_range=0.0,  # espectral: sin extensión espacial (dispara el bug del extent singular)
        y_range=0.0,
        group="Spectrum FFT",
        metadata={"Dim0Name": "Frequency", "Dim0Unit": "Hz", "Dim0Range": 1e5, "Dim0Min": 0.0},
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = render_channel(ch)
    ax = fig.axes[0]
    assert ax.lines and not ax.images  # línea, no imshow
    assert not any("singular" in str(w.message).lower() for w in caught)
    assert "Frequency (Hz)" in ax.get_xlabel()  # eje X = Dim0 con unidad

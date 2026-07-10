"""Genera las capturas y GIFs del README a partir de **datos sintéticos** (reproducible).

Maneja Fathom headless (offscreen), carga data sintética por los hubs reales y captura
cada perspectiva a ``docs/images/``. No usa ningún dato de instrumento: todo se genera
aquí con semillas fijas, así cualquiera puede regenerar los medios del README::

    QT_QPA_PLATFORM=offscreen python scripts/gen_docs_media.py

Requiere el extra ``gui`` (PyQt6 + pyqtgraph) y ``viz``.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication

from spmkit.core.analysis import resonance
from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume, SPMChannel, SPMData
from spmkit.gui.app_workspace import build_workspace
from spmkit.gui.viewmodels.evaporation_vm import EvaporationResult

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20240101)


# --------------------------------------------------------------- data sintética
def topography() -> SPMData:
    """Topografía con dos montículos gaussianos + granos finos y un canal CPD."""
    n = 160
    yy, xx = np.mgrid[0:n, 0:n]
    z = (
        4e-8 * np.exp(-((xx - 55) ** 2 + (yy - 60) ** 2) / 260.0)
        + 2.6e-8 * np.exp(-((xx - 110) ** 2 + (yy - 95) ** 2) / 160.0)
        + 6e-9 * RNG.standard_normal((n, n))
    )
    cpd = 0.25 + 0.12 * np.exp(-((xx - 80) ** 2 + (yy - 80) ** 2) / 900.0)
    cpd = cpd + 2e-3 * RNG.standard_normal((n, n))
    return SPMData(
        channels=(
            SPMChannel("Height", z, "m", 6e-6, 6e-6, direction="forward"),
            SPMChannel("CPD", cpd, "V", 6e-6, 6e-6, direction="forward"),
        ),
        metadata={"format": "nid"},
    )


def _hertz_curve(young: float, noise: float = 0.0) -> ForceCurve:
    sep = np.linspace(6e-7, 0.0, 400)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    delta = np.clip(3e-7 - sep, 0.0, None)
    force = k * delta**1.5
    if noise:
        force = force + noise * force.max() * RNG.standard_normal(force.size)
    z0 = np.zeros_like(sep)
    seg = lambda kind, direction: ForceSegment(  # noqa: E731
        segment_type=kind,
        direction=direction,
        raw_height=sep,
        raw_deflection=z0,
        deflection=z0,
        force=force,
        separation=sep,
        state="force_n",
    )
    return ForceCurve(segments=(seg("extend", "approach"), seg("retract", "retract")))


def force_curve_volume() -> ForceVolume:
    return ForceVolume.from_curves(
        (_hertz_curve(1.2e6, noise=0.015),), grid_shape=(1, 1), x_range=1e-6, y_range=1e-6
    )


def force_map_volume(side: int = 16) -> ForceVolume:
    """Grilla con módulo que varía espacialmente (dos dominios blando/duro)."""
    yy, xx = np.mgrid[0:side, 0:side]
    soft = 0.5e6 + 0.4e6 * np.exp(-((xx - 5) ** 2 + (yy - 5) ** 2) / 20.0)
    hard = 3.0e6 * np.exp(-((xx - 11) ** 2 + (yy - 11) ** 2) / 24.0)
    young = (soft + hard).ravel()
    curves = tuple(_hertz_curve(float(y), noise=0.02) for y in young)
    return ForceVolume.from_curves(curves, grid_shape=(side, side), x_range=4e-6, y_range=4e-6)


def thermal_spectrum(f0: float = 72_800.0, q: float = 106.0) -> SPMData:
    n = 2000
    f = np.linspace(30e3, 120e3, n)
    r = f / f0
    psd = 1e-12 / np.sqrt((1 - r**2) ** 2 + (r / q) ** 2) + 4e-14 * RNG.standard_normal(n)
    ch = SPMChannel(
        "Amplitude Spectral Density",
        np.abs(psd).reshape(1, -1),
        "m",
        1.0,
        1.0,
        group="Spectrum FFT",
        metadata={"Dim0Min": 30e3, "Dim0Range": 90e3},
    )
    return SPMData(
        channels=(ch,),
        metadata={
            "info": {
                "Frequency:": "72.8 kHz",
                "Q Factor:": "106",
                "Spring Constant:": "1.175 N/m",
            }
        },
    )


def evaporation_result() -> EvaporationResult:
    """Serie de evaporación sintética (f sube al perder masa) → ley d²."""
    t = np.linspace(0, 20 * 3600, 12)
    f = 79_000.0 - 6200.0 * np.exp(-t / (6 * 3600))
    series = resonance.track_evaporation(t, f, spring_constant=1.175)
    radius = np.asarray(resonance.droplet_radius(series.added_mass), dtype=np.float64)
    d2 = resonance.fit_d2_law(series.time, radius)
    return EvaporationResult(series=series, radius=radius, d2=d2)


# --------------------------------------------------------------- captura
def main() -> None:
    app = QApplication.instance() or QApplication([])
    ws = build_workspace()
    ws.resize(1360, 860)
    ws.show()
    app.processEvents()

    def snap(name: str) -> None:
        app.processEvents()
        ws.grab().save(str(OUT / name))
        print("  ✓", name)

    image_vm = ws.panel("navigator")._image_vm
    force_vm = ws.panel("force_canvas")._vm

    # Imagen + Granos (topografía)
    image_vm.set_data(topography())
    ws.set_perspective("image")
    snap("fathom_image.png")
    ws.set_perspective("grains")
    snap("fathom_grains.png")

    # Sintonía térmica (espectro)
    image_vm.set_data(thermal_spectrum())
    ws.set_perspective("resonance")
    snap("fathom_resonance.png")

    # Evaporación (serie sintética inyectada al panel)
    ws.set_perspective("evaporation")
    ws.panel("evaporation_canvas")._on_result(evaporation_result())
    snap("fathom_evaporation.png")

    # Curva de fuerza (hero) + Mapa de módulo
    force_vm.set_volume(force_curve_volume())
    force_vm.run_fit_now()
    ws.set_perspective("force")
    snap("fathom_force.png")

    force_vm.set_volume(force_map_volume())
    force_vm.run_fit_now()
    ws.set_perspective("map")
    ws.panel("map_canvas")._vm.compute_now("fast_cpu")
    snap("fathom_map.png")

    # GIF: recorrido por las perspectivas (cada frame vía PNG temporal + PIL)
    import tempfile

    from PIL import Image

    image_vm.set_data(topography())
    force_vm.set_volume(force_curve_volume())
    force_vm.run_fit_now()
    tour = ["image", "grains", "spectral", "resonance", "force", "map", "figure", "view3d"]
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, key in enumerate(tour):
            ws.set_perspective(key)
            app.processEvents()
            fp = f"{tmp}/frame_{i}.png"
            ws.grab().save(fp)
            frames.append(Image.open(fp).convert("RGB").resize((680, 430)))
        frames[0].save(
            OUT / "fathom_tour.gif",
            save_all=True,
            append_images=frames[1:],
            duration=1100,
            loop=0,
        )
    print("  ✓ fathom_tour.gif")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from spmkit_phantoms.surfaces import (
    flat_surface,
    gaussian_particles,
    inclined_plane,
    sinusoidal_surface,
    step_surface,
)

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "ecosystem" / "phantoms"
OUTPUT.mkdir(parents=True, exist_ok=True)


def render(name: str, title: str, phantom) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.0), constrained_layout=True)
    image = ax.imshow(
        phantom.z_data * 1e9,
        origin="lower",
        extent=(0, phantom.x_size_m * 1e6, 0, phantom.y_size_m * 1e6),
        cmap="magma",
        interpolation="nearest",
    )
    ax.set_title(title)
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    colorbar = fig.colorbar(image, ax=ax, shrink=0.82)
    colorbar.set_label("z (nm)")
    fig.savefig(OUTPUT / f"{name}.png", dpi=140, facecolor="#0b0e13")
    plt.close(fig)


def main() -> None:
    shape = (128, 128)
    x_size = y_size = 10e-6
    render("flat", "Flat surface · height 2 nm", flat_surface(shape, x_size, y_size, 2e-9))
    render(
        "inclined",
        "Inclined plane · known dz/dx and dz/dy",
        inclined_plane(shape, x_size, y_size, 0.002, -0.001),
    )
    render(
        "sinusoidal",
        "Sinusoidal surface · A = 5 nm, T = 2 µm",
        sinusoidal_surface(shape, x_size, y_size, 5e-9, 2e-6, 2e-6),
    )
    render("step", "Step surface · height 8 nm", step_surface(shape, x_size, y_size, 8e-9))
    render(
        "particles",
        "Gaussian particles · deterministic seed 42",
        gaussian_particles(shape, x_size, y_size, 12, 0.35e-6, 7e-9, 42),
    )


if __name__ == "__main__":
    main()

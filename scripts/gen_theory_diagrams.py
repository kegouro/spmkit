from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle

matplotlib.rcParams["svg.hashsalt"] = "spmkit-theory-v1"

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "theory"
OUT.mkdir(parents=True, exist_ok=True)
BG = "#0b0e13"
SURFACE = "#171f2a"
TEXT = "#e8eef5"
MUTED = "#93a0ae"
TEAL = "#2dd4bf"
GOLD = "#e8a94b"
GRID = "#33404f"


def setup(width: float = 9.6, height: float = 3.6):
    fig, ax = plt.subplots(figsize=(width, height), facecolor=BG)
    ax.set_facecolor(BG)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    return fig, ax


def save(fig, name: str) -> None:
    path = OUT / name
    fig.savefig(
        path,
        facecolor=BG,
        bbox_inches="tight",
        metadata={"Date": None, "Creator": "SPM-Kit theory diagram generator"},
    )
    plt.close(fig)
    normalized = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())
    path.write_text(normalized + "\n", encoding="utf-8")


def afm_instrument() -> None:
    fig, ax = setup(height=3.4)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.add_patch(Rectangle((0.4, 0.35), 2.2, 0.28, color=GRID))
    x = np.linspace(0.5, 2.5, 180)
    ax.plot(x, 0.65 + 0.12 * np.sin(x * 9), color=GOLD, lw=2)
    ax.add_patch(Polygon([[1.4, 1.75], [1.7, 0.72], [1.95, 1.75]], color=TEXT))
    ax.add_patch(Rectangle((1.15, 1.72), 2.2, 0.17, angle=8, color=TEAL))
    ax.add_patch(Circle((3.5, 3.2), 0.12, color=GOLD))
    ax.plot([3.5, 2.55], [3.2, 1.9], color=GOLD, lw=2)
    ax.plot([2.55, 5.2], [1.9, 3.0], color=GOLD, lw=2)
    ax.add_patch(Rectangle((5.2, 2.55), 1.3, 0.9, edgecolor=TEXT, facecolor=SURFACE, lw=1.5))
    for label, x0 in [("A", 5.55), ("B", 6.15)]:
        ax.text(x0, 3.2, label, color=TEXT, ha="center", va="center")
    for label, x0 in [("C", 5.55), ("D", 6.15)]:
        ax.text(x0, 2.8, label, color=TEXT, ha="center", va="center")
    nodes = [
        (1.6, 0.12, "sample + scanner"),
        (2.2, 2.2, "tip + cantilever"),
        (3.5, 3.55, "laser"),
        (5.85, 3.75, "quadrant detector"),
        (8.2, 2.75, "feedback"),
        (8.2, 0.9, "Z command → topography"),
    ]
    for x0, y0, label in nodes:
        ax.text(x0, y0, label, color=TEXT, ha="center", fontsize=9)
    ax.add_patch(FancyArrowPatch((6.6, 3.0), (7.6, 2.8), arrowstyle="->", color=TEAL, lw=2))
    ax.add_patch(FancyArrowPatch((8.2, 2.45), (8.2, 1.25), arrowstyle="->", color=TEAL, lw=2))
    ax.add_patch(FancyArrowPatch((7.5, 0.9), (2.75, 0.55), arrowstyle="->", color=TEAL, lw=2))
    ax.text(
        5.1,
        0.2,
        "measured signal → error → scanner correction",
        color=MUTED,
        ha="center",
        fontsize=8,
    )
    save(fig, "afm-instrument.svg")


def operating_modes() -> None:
    fig, axes = plt.subplots(1, 5, figsize=(11.2, 3.0), facecolor=BG)
    labels = [
        ("Contact", "deflection", "continuous contact"),
        ("Tapping", "amplitude", "intermittent contact"),
        ("Non-contact", "frequency shift", "attractive regime"),
        ("Force volume", "force curve", "grid of ramps"),
        ("KPFM", "null voltage", "electrostatic feedback"),
    ]
    for i, (title, measured, regime) in enumerate(labels):
        ax = axes[i]
        ax.set_facecolor(BG)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.plot([0.08, 0.92], [0.18, 0.18], color=GOLD, lw=2)
        ax.add_patch(Polygon([[0.45, 0.65], [0.5, 0.27], [0.55, 0.65]], color=TEXT))
        if i in {1, 2, 4}:
            ax.add_patch(Arc((0.5, 0.58), 0.55, 0.48, theta1=210, theta2=510, color=TEAL, lw=2))
        if i == 3:
            for x0 in [0.2, 0.4, 0.6, 0.8]:
                ax.add_patch(
                    FancyArrowPatch((x0, 0.7), (x0, 0.25), arrowstyle="<->", color=TEAL, lw=1.3)
                )
        ax.text(0.5, 0.92, title, color=TEXT, ha="center", weight="bold")
        ax.text(0.5, 0.08, measured, color=TEAL, ha="center", fontsize=8)
        ax.text(0.5, -0.01, regime, color=MUTED, ha="center", fontsize=7)
    save(fig, "operating-modes.svg")


def force_curve() -> None:
    fig, ax = setup(height=4.2)
    x = np.linspace(-1.0, 1.0, 500)
    approach = np.where(
        x < 0.02,
        -0.10 * np.exp(-(((x + 0.05) / 0.08) ** 2)),
        1.45 * np.clip(x - 0.02, 0, None) ** 1.5,
    )
    retract = np.where(
        x < 0.28,
        -0.42 * np.exp(-(((x - 0.1) / 0.18) ** 2)),
        1.18 * np.clip(x - 0.28, 0, None) ** 1.5,
    )
    ax.plot(x, approach, color=TEAL, lw=2.5, label="approach")
    ax.plot(x, retract, color=GOLD, lw=2.5, label="retract")
    ax.axhline(0, color=GRID, lw=1)
    ax.axvline(0, color=GRID, lw=1, ls="--")
    ax.annotate(
        "baseline",
        (-0.72, 0.02),
        (-0.82, 0.45),
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    ax.annotate(
        "snap-in",
        (-0.05, -0.1),
        (-0.45, -0.42),
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    ax.annotate(
        "contact / fit window",
        (0.56, 0.58),
        (0.25, 1.1),
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    idx = int(np.argmin(retract))
    ax.annotate(
        "pull-off / adhesion",
        (x[idx], retract[idx]),
        (0.38, -0.58),
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    ax.fill_between(
        x,
        approach,
        retract,
        where=(x > -0.05) & (x < 0.52),
        color=TEAL,
        alpha=0.12,
        label="hysteresis area",
    )
    ax.set_xlabel("tip–sample separation / ramp coordinate", color=TEXT)
    ax.set_ylabel("force", color=TEXT)
    ax.legend(frameon=False, labelcolor=TEXT, loc="upper left")
    save(fig, "force-distance.svg")


def contact_geometry() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), facecolor=BG)
    for ax in axes:
        ax.set_facecolor(BG)
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.3, 1.35)
        ax.axis("off")
        ax.plot([-1.1, 1.1], [0, 0], color=GOLD, lw=2)
        ax.plot([0, 0], [0, 0.7], color=MUTED, ls="--")
        ax.add_patch(
            FancyArrowPatch((0.72, 0.82), (0.72, 0.05), arrowstyle="<->", color=TEAL, lw=1.5)
        )
        ax.text(0.79, 0.42, "δ", color=TEAL, fontsize=13)
    axes[0].add_patch(Circle((0, 1.0), 0.78, edgecolor=TEXT, facecolor="none", lw=2))
    axes[0].text(0, 1.28, "Hertz / paraboloid", ha="center", color=TEXT, weight="bold")
    axes[0].text(
        0, -0.2, r"$F=\frac{4}{3}E^*\sqrt{R}\,\delta^{3/2}$", ha="center", color=TEXT, fontsize=13
    )
    axes[0].annotate(
        "R", (0.45, 0.6), (0.9, 1.1), color=TEXT, arrowprops={"arrowstyle": "->", "color": MUTED}
    )
    axes[1].plot([-1.0, 0, 1.0], [1.25, 0.02, 1.25], color=TEXT, lw=2)
    axes[1].add_patch(Arc((0, 0.7), 0.7, 0.7, theta1=248, theta2=292, color=TEAL, lw=1.5))
    axes[1].text(0.18, 0.82, "α", color=TEAL, fontsize=13)
    axes[1].text(0, 1.28, "Sneddon cone", ha="center", color=TEXT, weight="bold")
    axes[1].text(
        0, -0.2, r"$F=\frac{2}{\pi}E^*\tan(\alpha)\,\delta^2$", ha="center", color=TEXT, fontsize=13
    )
    save(fig, "contact-geometries.svg")


def kpfm_energy() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), facecolor=BG)
    for ax in axes:
        ax.set_facecolor(BG)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    axes[0].text(0.5, 0.92, "Separated", ha="center", color=TEXT, weight="bold")
    axes[0].hlines([0.62, 0.36], [0.08, 0.58], [0.42, 0.92], colors=[TEAL, GOLD], lw=3)
    axes[0].text(0.25, 0.67, "tip Fermi level", color=TEAL, ha="center", fontsize=8)
    axes[0].text(0.75, 0.41, "sample Fermi level", color=GOLD, ha="center", fontsize=8)
    axes[0].add_patch(FancyArrowPatch((0.49, 0.36), (0.49, 0.62), arrowstyle="<->", color=TEXT))
    axes[0].text(0.52, 0.49, r"$eV_{CPD}$", color=TEXT)
    axes[1].text(
        0.5, 0.92, "Electrical connection + DC null", ha="center", color=TEXT, weight="bold"
    )
    axes[1].hlines(0.5, 0.08, 0.92, colors=TEAL, lw=3)
    axes[1].text(
        0.5, 0.56, "aligned electrochemical potential", color=TEAL, ha="center", fontsize=8
    )
    axes[1].add_patch(FancyArrowPatch((0.22, 0.2), (0.78, 0.2), arrowstyle="<->", color=GOLD, lw=2))
    axes[1].text(0.5, 0.1, r"feedback drives $V_{DC}\rightarrow V_{CPD}$", color=GOLD, ha="center")
    save(fig, "kpfm-energy.svg")


def roughness_flow() -> None:
    fig, ax = setup(height=2.6)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.2)
    ax.axis("off")
    labels = [
        ("raw height", "unit + field of view"),
        ("mask / select", "invalid pixels"),
        ("level", "plane/poly/rows"),
        ("measure", "Sa Sq Sz Ssk Sku"),
        ("preserve", "parameters + result"),
    ]
    for i, (title, sub) in enumerate(labels):
        x0 = 0.2 + i * 2
        ax.add_patch(
            Rectangle(
                (x0, 0.65), 1.55, 0.9, facecolor=SURFACE, edgecolor=TEAL if i == 2 else GRID, lw=1.5
            )
        )
        ax.text(x0 + 0.775, 1.2, title, color=TEXT, ha="center", weight="bold", fontsize=9)
        ax.text(x0 + 0.775, 0.87, sub, color=MUTED, ha="center", fontsize=7)
        if i < 4:
            ax.add_patch(
                FancyArrowPatch(
                    (x0 + 1.58, 1.1), (x0 + 1.95, 1.1), arrowstyle="->", color=GOLD, lw=1.5
                )
            )
    ax.text(
        5,
        0.28,
        "Preprocessing changes the reference surface and therefore the reported metrics.",
        color=GOLD,
        ha="center",
        fontsize=8,
    )
    save(fig, "roughness-flow.svg")


def psd_plot() -> None:
    fig, ax = setup(height=4.0)
    q = np.logspace(5, 9, 400)
    q0 = 2.2e7
    beta = 3.2
    psd = 1 / (1 + (q / q0) ** beta)
    ax.loglog(q, psd, color=TEAL, lw=2.5)
    ax.axvline(q0, color=GOLD, ls="--", lw=1.5)
    ax.text(q0 * 1.15, 0.25, r"roll-off $q_0$", color=GOLD)
    ax.annotate(
        r"self-affine slope $-\beta$",
        (2e8, psd[np.searchsorted(q, 2e8)]),
        (6e7, 3e-3),
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    ax.text(1.4e5, 0.55, "finite-size plateau", color=TEXT)
    ax.set_xlabel(r"spatial frequency $q$ (m$^{-1}$)", color=TEXT)
    ax.set_ylabel("radially averaged PSD", color=TEXT)
    ax.grid(True, which="both", color=GRID, alpha=0.35)
    save(fig, "psd-interpretation.svg")


def resonance_plot() -> None:
    fig, ax = setup(height=4.0)
    f = np.linspace(60, 90, 1400)

    def peak(f0, q):
        ratio = f / f0
        return 1 / np.sqrt((1 - ratio**2) ** 2 + (ratio / q) ** 2)

    bare = peak(78, 95)
    loaded = peak(73.5, 82)
    ax.plot(f, bare, color=TEAL, lw=2.3, label="bare")
    ax.plot(f, loaded, color=GOLD, lw=2.3, label="loaded")
    ax.axvline(78, color=TEAL, ls="--", alpha=0.6)
    ax.axvline(73.5, color=GOLD, ls="--", alpha=0.6)
    ax.add_patch(
        FancyArrowPatch(
            (73.5, max(loaded) * 0.2), (78, max(loaded) * 0.2), arrowstyle="<->", color=TEXT
        )
    )
    ax.text(75.75, max(loaded) * 0.24, r"$\Delta f<0$ for added mass", color=TEXT, ha="center")
    ax.set_xlabel("frequency (kHz)", color=TEXT)
    ax.set_ylabel("response amplitude (relative)", color=TEXT)
    ax.legend(frameon=False, labelcolor=TEXT)
    ax.grid(True, color=GRID, alpha=0.35)
    save(fig, "resonance-response.svg")


def software_architecture() -> None:
    fig, ax = setup(height=3.4)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    blocks = [
        ("instrument files", 0.3, 1.5, 1.6, 0.9, GRID),
        ("readers +\ndomain models", 2.4, 1.5, 1.6, 0.9, TEAL),
        ("pure analysis", 4.5, 1.5, 1.5, 0.9, TEAL),
        ("typed results", 6.5, 1.5, 1.4, 0.9, TEAL),
    ]
    for label, x0, y0, w, h, color in blocks:
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=SURFACE, edgecolor=color, lw=1.6))
        ax.text(x0 + w / 2, y0 + h / 2, label, color=TEXT, ha="center", va="center", fontsize=9)
    for start, end in [
        ((1.9, 1.95), (2.35, 1.95)),
        ((4.0, 1.95), (4.45, 1.95)),
        ((6.0, 1.95), (6.45, 1.95)),
    ]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", color=GOLD, lw=1.5))
    for label, x0 in [("Python API", 6.0), ("CLI", 7.3), ("Fathom", 8.6)]:
        ax.add_patch(Rectangle((x0, 3.05), 1.1, 0.55, facecolor=SURFACE, edgecolor=GOLD, lw=1.3))
        ax.text(x0 + 0.55, 3.325, label, color=TEXT, ha="center", va="center", fontsize=8)
        ax.add_patch(
            FancyArrowPatch((7.2, 2.45), (x0 + 0.55, 3.0), arrowstyle="->", color=MUTED, lw=1.1)
        )
    ax.add_patch(Rectangle((8.35, 1.5), 1.35, 0.9, facecolor=SURFACE, edgecolor=GOLD, lw=1.6))
    ax.text(9.025, 1.95, "exports +\nprovenance", color=TEXT, ha="center", va="center", fontsize=9)
    ax.add_patch(FancyArrowPatch((7.9, 1.95), (8.3, 1.95), arrowstyle="->", color=GOLD, lw=1.5))
    ax.text(
        5,
        0.55,
        "Core owns computation. Presentation layers orchestrate public Core APIs.",
        color=GOLD,
        ha="center",
        fontsize=9,
    )
    save(fig, "software-architecture.svg")


def main() -> None:
    afm_instrument()
    operating_modes()
    force_curve()
    contact_geometry()
    kpfm_energy()
    roughness_flow()
    psd_plot()
    resonance_plot()
    software_architecture()


if __name__ == "__main__":
    main()

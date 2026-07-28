# Resonance & mass sensing

Here the cantilever stops being just a topography sensor and becomes a
**balance**. The idea is elegant: if we know its stiffness and measure how its
resonance frequency changes, we can weigh **nanograms**.

## The cantilever as a harmonic oscillator

Modeled as mass-spring, its resonance frequency is:

$$
f_0 = \frac{1}{2\pi} \sqrt{\frac{k}{m_{\text{eff}}}}
$$

```text
   cantilever (spring k, mass m_eff)
              ●(loaded with mass Δm on the tip)
            ╱│
           ╱ │ ← flexural mode
          ╱  │
    ══════●   ●══════
              f_0  lowers as Δm grows
        ┌─────────────────────┐
   amp  │     ●bare           │
        │    ╱│╲               │
        │   ╱ │ ╲     ●loaded  │
        │  ╱  │  ╲   ╱│╲       │
        │ ╱   │   ╲ ╱ │  ╲     │
        │╱    │    ●   │   ╲   │
        └─────┴───┴───┴────┴──► f
              f_bare    f_loaded
              ◄── Δf ──►
```

*migrated from `docs/assets/legacy/theory-standalone.html` §07 (loaded cantilever
and resonance-shift SVGs); combined here as a single static ASCII figure showing
both the loaded oscillator and the resulting downward frequency shift.*

$k$ is the spring constant (N/m), $m_{\text{eff}}$ is the effective mass of
the mode. More mass → lower frequency.

## Quality factor Q

The **quality factor** $Q = f_0 / \Delta f_{\text{FWHM}}$ measures how "sharp"
the resonance peak is (how lightly damped it is). A high Q means narrow peaks
and therefore better frequency resolution: the basis of mass-sensing
sensitivity.

## Thermal noise and equipartition → calibrate k

At temperature $T$, molecular collisions agitate the cantilever. By the
**equipartition theorem**, each quadratic degree of freedom carries
$\frac{1}{2} k_B T$ of energy. For the cantilever mode:

$$
\frac{1}{2} k \langle x^2 \rangle = \frac{1}{2} k_B T
\quad \Longrightarrow \quad
\langle x^2 \rangle = \frac{k_B T}{k}
$$

Measuring the thermal noise variance $\langle x^2 \rangle$ yields
$k = k_B T / \langle x^2 \rangle$. This is **thermal tuning**: calibrating
the spring without touching the sample.

## Mass sensing by frequency shift

Solving for the effective mass and inverting the resonance relation:

$$
m_{\text{eff}} = \frac{k}{(2\pi f)^2}
$$

The **added mass** relative to the bare cantilever (at frequency
$f_{\text{bare}}$) is:

$$
\Delta m = \frac{k}{4\pi^2} \left( \frac{1}{f^2} - \frac{1}{f_{\text{bare}}^2} \right)
$$

and for small $\Delta m$, linearizes to:

$$
\frac{\Delta f}{f_0} \approx -\frac{\Delta m}{2 m_{\text{eff}}}
\quad \Longrightarrow \quad
\Delta f \propto \Delta m
$$

!!! definition "Physical interpretation"

    Adding mass *lowers* the frequency (loaded spring oscillates slower). If
    that mass *changes over time* (e.g. because it evaporates, adsorbs, or
    reacts), tracking $f(t)$ reconstructs $\Delta m(t)$: a **dynamic balance**
    with sub-nanogram resolution.

## d² evaporation law

For a drop evaporating by diffusion, the **square of the diameter** decreases
linearly in time: $d^2(t) = d_0^2 - K \cdot t$. Since mass goes as $d^3$, this
classical law predicts how $\Delta m(t)$ — and therefore $f(t)$ — should
evolve during evaporation, allowing direct comparison between theory and
measurement in SPM-Kit.

!!! implementation "In SPM-Kit"

    The resonance module reads NanoSurf thermal tuning spectra, detects the
    peak ($f_0$, $Q$, FWHM), and over a time series computes $f(t)$,
    $\Delta m(t)$, and the **evaporation rate** $d\Delta m/dt$. The
    **Resonance** perspective graphs the full cycle.

---

## Evidence status

| Concept | Where | Status |
|---|---|---|
| SHO fit ($f_0$, $Q$) | `spmkit.core.analysis.resonance` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Thermal tuning ($k$ calibration) | `spmkit.core.analysis.resonance` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Mass sensing ($\Delta m$) | `spmkit.core.analysis.resonance` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |

Recovery test: $f_0$ and $Q$ recovered at 0.01% / 4% vs a real instrument.

[:material-arrow-left: Roughness & spectral analysis](roughness.md) · [:material-arrow-right: SPM-Kit workflows](spmkit-workflows.md)

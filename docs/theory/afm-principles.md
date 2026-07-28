# AFM principles

## What is the AFM?

The atomic force microscope (AFM) is, in essence, a nanometric finger. Instead
of lenses and light, it uses a **sharp tip** — with a radius of just a few
nanometers — mounted on the end of a flexible **cantilever** that scans the
surface line by line.

When the tip approaches the sample, **tip-sample forces** appear: van der Waals
attraction at medium distances, Pauli repulsion on contact, plus adhesion,
capillarity, and electrostatic forces. These forces *bend* the cantilever. The
cantilever behaves as a spring of constant $k$ (Hooke's law, $F = -k \cdot z$),
so measuring its deflection is equivalent to measuring the force.

## The optical lever trick

The deflection is minuscule (fractions of a nanometer), so it is amplified
optically: a **laser** strikes the back of the cantilever and reflects onto a
**four-quadrant photodiode**. A tiny tilt of the lever displaces the laser spot
by several millimeters on the photodiode: geometric gain for free.

A **feedback loop** compares the photodiode signal with a setpoint value and
commands the **piezoelectric scanner** to raise or lower the sample to keep
the interaction constant. The correction signal, point by point, *is* the
topography.

!!! definition "Key physics"

    The AFM does not require the sample to conduct (unlike STM). It resolves
    **sub-nanometric heights** and **piconewton forces** because it converts a
    tiny mechanical deflection into a large optical signal, and because a fast
    loop prevents the tip from "crashing" into the surface.

---

## Implementation in SPM-Kit

| Concept | Where | Status |
|---|---|---|
| Topography reading | `spmkit.core.io` (`.nid`, `.nhf`, `.gwy` readers) | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| Leveling (plane, polynomial, per-row) | `spmkit.core.analysis` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| Line profiles (bilinear interpolation) | `spmkit.core.analysis` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |

[:material-arrow-left: Theory overview](index.md) · [:material-arrow-right: Operating modes](operating-modes.md)

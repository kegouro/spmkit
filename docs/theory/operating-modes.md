# Operating modes

Depending on what quantity the feedback loop keeps constant, the AFM operates
in different regimes. The choice balances **resolution**, **gentleness** with
the sample, and **speed**.

## Contact mode

The tip "touches" the sample and the loop keeps the **deflection** (normal
force) constant. It is simple and fast, but lateral forces can scratch soft
samples or wear the tip.

## Dynamic / tapping (intermittent contact)

The cantilever is excited near its resonance frequency $f_0$ and oscillates;
as it approaches the surface, the interaction **reduces the amplitude**. The
loop keeps that amplitude constant. Since the tip only "taps" briefly, it
nearly eliminates lateral forces: ideal for polymers, cells, and fragile
samples.

## Non-contact

The cantilever oscillates in the *attractive* regime without touching the
surface; the **frequency shift** due to the force gradient is detected.
Maximum gentleness and, in ultra-high vacuum, atomic resolution, at the cost
of environmental sensitivity.

| Mode | Control signal | Force regime | Advantage | Risk / cost |
|---|---|---|---|---|
| **Contact** | `deflection = const` | repulsive | simple, fast, high z-resolution | lateral forces; wear |
| **Tapping** | `amplitude = const` | attract.↔repuls. | low damage; standard in air | slower; fine tuning |
| **Non-contact** | `Δf = const` | attractive | very gentle; atomic resolution (UHV) | environment-sensitive |

!!! note "Connection"

    Tapping and non-contact share the same physical root — an oscillating
    cantilever — formalized in [Resonance & mass sensing](resonance.md). The
    difference is only *which observable* of the resonance is fed back:
    amplitude or frequency.

---

## Implementation in SPM-Kit

| Concept | Where | Status |
|---|---|---|
| `.nid` topography (contact/tapping) | `spmkit.core.io.nanosurf` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| `.gwy` multi-channel (topography + KPFM) | `spmkit.core.io.gwyddion` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |

[:material-arrow-left: AFM principles](afm-principles.md) · [:material-arrow-right: Force-distance curves](force-distance.md)

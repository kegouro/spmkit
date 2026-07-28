# Force-distance curves

If instead of scanning we park the tip at a point and move it toward and away
from the surface, we record the **force as a function of separation**. This
F-d curve (or force spectroscopy) is the local mechanical fingerprint of the
sample.

## Regions of the curve

```text
  F
  ▲
  │      approach (teal)
  │        ╱── contact slope → modulus
  │       ╱
  │  ╲   ╱
  │   ╲ ╱      snap-in
  │    ●            ←────────── retract (gold)
  │   ╱           ╲
  │  ╱             ╲      pull-off
  │ ╱               ●─────● (adhesion)
  │/                    ↑
  └───────────────────────► z (tip-sample separation)
   non-contact   contact   contact  non-contact
```

**Approach** (teal): the tip first feels nothing; as the attractive gradient
enters, it snaps into contact (**snap-in**) and then rises through the
repulsive region with a **contact slope** that encodes stiffness.

**Retract** (gold): adhesion retains the tip until the **pull-off**: the depth
of that minimum measures the adhesion force. The area between both branches is
the hysteresis (dissipated energy).

*migrated from `docs/assets/legacy/theory-standalone.html` §03 (F-d curve
regions SVG); the static ASCII version preserves the annotated regions in the
native build.*

## Analysis

The curve regions feed two distinct analyses: the **contact slope** gives the
[elastic modulus](contact-mechanics.md), and the **pull-off depth** gives the
**adhesion**. SPM-Kit first corrects the baseline (non-contact region) and
detects the contact point before fitting.

!!! implementation "In SPM-Kit"

    `spmkit.core.analysis.forcecurve` handles baseline correction, contact-point
    detection, and model fitting. The **Nanomechanics** perspective in Fathom
    shows the fit and builds modulus maps.

---

## Evidence status

| Concept | Where | Status |
|---|---|---|
| Hertz/DMT/JKR fit | `spmkit.core.analysis.forcecurve` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| WLC/FJC fit | `spmkit.core.analysis.forcecurve` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Force-volume maps | `spmkit.core.analysis.forcevolume_fast` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |
| Event detection (SMFS) | `spmkit.core.analysis.smfs` | <span class="level-badge level-2">LEVEL 2 NUMERICALLY_VERIFIED</span> |

[:material-arrow-left: Operating modes](operating-modes.md) · [:material-arrow-right: Contact mechanics](contact-mechanics.md)

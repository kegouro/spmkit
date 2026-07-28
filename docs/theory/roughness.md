# Roughness & spectral analysis

Once the image is leveled, its **texture** is summarized with statistical
parameters (ISO 25178) and with its **spatial spectrum**, which reveals how
roughness is distributed across scales.

## Area parameters (ISO 25178)

| Parameter | Definition | What it tells you |
|---|---|---|
| `Sa` | mean of \|height\| | average roughness (robust) |
| `Sq` | root mean square (RMS) | RMS roughness; weights peaks more |
| `Sz` | max peak + max valley | extreme amplitude |
| `Ssk` | skewness | >0 peaks dominate; <0 valleys dominate |
| `Sku` | kurtosis | >3 "peaked" distribution; <3 flat |

## Radial PSD, Hurst and fractal dimension

The power spectral density (**PSD**) radially averaged shows how power decays
with spatial frequency $q$. Many surfaces are **self-affine**: their PSD
follows a power law $\text{PSD}(q) \propto q^{-\beta}$. The exponent $\beta$
relates to the **Hurst exponent** $H$ and the **fractal dimension** $D$:

$$
\beta = 2H + 2
$$

$$
D = 3 - H
$$

$H \to 1$: smooth surface ($D \to 2$) · $H \to 0$: very rough ($D \to 3$).

Additionally, the **correlation length** marks the scale beyond which heights
are no longer correlated: it separates the self-affine regime (short scales)
from the saturated regime (long scales). Together, these descriptors
characterize texture in a way that is independent of image size.

!!! implementation "In SPM-Kit"

    The roughness module computes Sa/Sq/Sz/Ssk/Sku after leveling (plane,
    polynomial, or per-row); the spectral module delivers radial PSD, Hurst
    exponent, fractal dimension, and correlation length. All accessible from
    the **Viewer** perspective.

---

## Evidence status

| Concept | Where | Status |
|---|---|---|
| ISO 25178 roughness | `spmkit.core.analysis.roughness` | <span class="level-badge level-3">LEVEL 3 CROSS_VALIDATED</span> |
| PSD / Hurst / fractal dimension | `spmkit.core.analysis.spectral` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |

Sa, Sq and Sz were externally cross-validated against Gwyddion 2.71 on 6
synthetic surfaces: **18/18 conforming comparisons**.

[:material-arrow-left: KPFM](kpfm.md) · [:material-arrow-right: Resonance & mass sensing](resonance.md)

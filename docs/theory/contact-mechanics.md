# Contact mechanics

Once in contact, the F-δ curve (force vs. *indentation*) is fit to a contact
mechanics model to extract the local **Young's modulus**. The model depends on
the tip geometry.

## Hertz contact (spherical / paraboloid tip)

$$
F = \frac{4}{3} E^* \sqrt{R} \cdot \delta^{3/2}
$$

with $R$ the tip radius, $\delta$ the indentation, $E^*$ the reduced modulus.
The characteristic **3/2 exponent** identifies the sphere.

## Sneddon contact (conical tip)

$$
F = \frac{2}{\pi} E^* \tan(\alpha) \cdot \delta^2
$$

with $\alpha$ the cone half-angle. The geometric footprint changes the
exponent to **2**.

## Reduced modulus and Young's modulus

$$
E^* = \frac{E}{1 - \nu^2}
$$

(rigid tip) · $E$ is the sample's Young's modulus, $\nu$ is Poisson's ratio.
In general:

$$
\frac{1}{E^*} = \frac{1-\nu_1^2}{E_1} + \frac{1-\nu_2^2}{E_2}
$$

The fit returns $E$ (in Pa), the contact point, the **adhesion**, and the fit
error (RMSE). Repeating this on a grid of points — **force-volume
spectroscopy** — produces a **modulus map**: an image where each pixel is the
local stiffness. This distinguishes hard and soft domains in a composite
material, with the same lateral resolution as the topography.

!!! implementation "In SPM-Kit"

    The mechanics module supports `sphere`/`paraboloid` (exponent 1.5) and
    `cone` (exponent 2.0) models, corrects the baseline, detects the contact
    point, and fits by least squares. The **Nanomechanics** perspective shows
    the Hertz fit and builds modulus maps.

---

## Evidence status

| Model | Recovery test | Tolerance |
|---|---|---|
| Hertz / DMT | Young's modulus from synthetic curves | < 2% with 1% noise |
| JKR (adhesive) | $E^*$, adhesion work | < 2% ($E^*$), Hertz limit $w=0$ |
| Sneddon (cone) | Young's modulus | < 2% |

All models pass **synthetic recovery tests** in
[`tests/validation/test_recovery.py`](https://github.com/kegouro/spmkit/blob/main/tests/validation/test_recovery.py).

[:material-arrow-left: Force-distance curves](force-distance.md) · [:material-arrow-right: KPFM](kpfm.md)

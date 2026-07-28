# KPFM — contact potential

Kelvin Probe Force Microscopy (KPFM) adds an electrical channel to the
topography: it measures the **contact potential difference** between tip and
sample, which is linked to their **work functions**.

## Contact potential difference (CPD)

When two materials with different work functions are connected, their Fermi
levels align and a contact potential difference appears:

$$
V_{\text{CPD}} = \frac{\phi_{\text{tip}} - \phi_{\text{sample}}}{e}
$$

$\phi$ is the work function (energy to extract an electron), $e$ is the
elementary charge. KPFM applies a DC voltage that nulls the electrostatic
force and thus *reads* $V_{\text{CPD}}$ point by point.

If the tip work function is known (calibrated against a standard), the sample
work function is obtained:

$$
\phi_{\text{sample}} = \phi_{\text{tip}} - e \cdot V_{\text{CPD}}
$$

The result is a work function map with chemical and doping contrast,
complementary to topography.

!!! implementation "In SPM-Kit"

    The KPFM module computes CPD statistics and, given the tip work function,
    the sample work function. In the GUI this lives in the **Viewer**
    perspective, alongside roughness and profiles.

---

## Evidence status

| Concept | Where | Status |
|---|---|---|
| KPFM CPD reading | `spmkit.core.io` (`.nid` KPFM channel) | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |
| Work function calculation | `spmkit.core.analysis` | <span class="level-badge level-1">LEVEL 1 SOFTWARE_VERIFIED</span> |

[:material-arrow-left: Contact mechanics](contact-mechanics.md) · [:material-arrow-right: Roughness & spectral analysis](roughness.md)

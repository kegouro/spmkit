# Fathom quick start

**SPM-Kit computes. Fathom lets the researcher inspect, configure and operate
those computations interactively.** Fathom is installed with SPM-Kit; it is not
a separate numerical package.

## First session

1. Install the GUI extra: `python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"`.
2. Launch `spmkit gui`, optionally followed by a file path.
3. Open a file with **Ctrl+O** or drag it onto the workspace.
4. Inspect the proposed routing. A mixed file may ask whether to open it as an image or force map.
5. Choose a perspective from the top bar or press **Ctrl+K** and search by name.
6. Configure the visible parameters. Record tip radius, fit model, leveling or thresholds when they affect the result.
7. Run the analysis and inspect the result, residuals, R² or other available quality indicators.
8. Export a figure/result/report as appropriate.
9. Save a `.spmproj` project with **Ctrl+S** when the workflow supports it.
10. Keep the source file, software version and exported provenance with the result.

## Which perspective?

| Intent | Display name in current code | Key |
|---|---|---|
| Topography, roughness and KPFM | Imagen | `image` |
| Particle segmentation | Granos | `grains` |
| PSD and self-affine analysis | Espectral | `spectral` |
| Cantilever spectrum | Sintonía térmica | `resonance` |
| Time-dependent resonance | Evaporación | `evaporation` |
| One force curve and contact fit | Curva de fuerza | `force` |
| Molecule-pulling events | SMFS | `smfs` |
| Force-volume properties | Mapa | `map` |
| Multiple files | Batch | `batch` |
| Publication output | Figura | `figure` |
| Surface rendering | Vista 3D | `view3d` |
| Educational cantilever simulation | Simulador | `simulator` |

Screenshots in this documentation are generated from deterministic synthetic
data by `scripts/gen_docs_media.py`; they are interface demonstrations, not
experimental validation.

[Open the complete Fathom tour](../ecosystem/fathom.md) ·
[Read the full manual](../user-guide.md)

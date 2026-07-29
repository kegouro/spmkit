---
title: Ecosystem brand governance
description: Official names, identities, canonical assets, palettes, and prohibited substitutions across the SPM-Kit ecosystem.
---

# Ecosystem brand governance

Consistency means coherent relationships, not identical appearances. The site
supplies the grid, typography, evidence vocabulary and interaction behavior;
each repository keeps its own canonical banner and role.

| Official name | Repository | Public subtitle | Banner source | Mark/logo | Accent | Preferred description |
|---|---|---|---|---|---|---|
| SPM-Kit Core | `kegouro/spmkit` | Numerical engine | `docs/images/brand/spmkit_banner_final.png` | Core square artwork remains archival; Fathom mark is not substituted for Core | warm gold `#E8A94B` | Headless numerical engine, Python API, CLI and plugin contracts for AFM/SPM analysis |
| Fathom | `kegouro/spmkit` | Interactive scientific workspace | `docs/images/brand/fathom_banner_new.jpeg` | `fathom_mark.svg`, `fathom_lockup.svg` | signal teal `#2DD4BF` + gold `#E8A94B` | Interactive workspace that operates the same SPM-Kit Core |
| SPM-Kit Data Hunter | `kegouro/spmkit-data-hunter` | Evidence discovery | `branding/banner.png` | `branding/logo.svg`; male/female marks optional | orange `#FB923C` | Discovers and classifies candidate public AFM/SPM evidence |
| SPM-Kit Phantoms | `kegouro/spmkit-phantoms` | Synthetic truth | `branding/main-banner.png` | banner-contained identity | amber `#F59E0B` | Generates deterministic analytical surfaces and controlled corruptions |
| SPM-Kit Validation | `kegouro/spmkit-validation` | External evidence | `docs/images/brand/spmkit-validation-banner.png` | banner-contained identity | cream + gold | Executes frozen public-interface campaigns and preserves evidence |

## Shared rules

- Write **SPM-Kit**, not `SPMKit`; use the lowercase spelling only inside
  package/repository identifiers such as `spmkit-validation`.
- Keep **Fathom** capitalized and describe it as the workspace, not a second analyzer.
- Do not stretch, crop or recolor canonical banners.
- Do not place overlay text on banner areas not designed for it.
- Keep component name/role in nearby text so identity does not depend on color.
- Use graphite, teal and warm gold as the common site frame; retain each companion's banner palette.
- Preserve intrinsic image dimensions, meaningful alt text and local copies.
- Label synthetic screenshots and generated phantom plots.

## Prohibited substitutions

- Fathom banner presented as SPM-Kit Core;
- Core described as a GUI or Fathom described as independent numerical software;
- Data Hunter presented as a validator/certifier;
- Phantoms presented as physical evidence or a complete microscope simulator;
- Validation presented as internal unit tests or every PASS as universal validity;
- acknowledgements converted into software authorship, institutional ownership or endorsement;
- the SPM Lab or Universidad Técnica Federico Santa María presented as software owner;
- remote raw-GitHub hotlinks used as production assets.

## Asset audit

The [machine-readable manifest](../assets/ecosystem/assets-manifest.yml) records
the audited commits, every discovered visual asset, true formats, dimensions,
bytes, transparency, use, duplicates, obsolete candidates, text concerns and
SHA-256. [Read the selection rationale](../assets/ecosystem/ASSETS.md).

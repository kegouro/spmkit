---
title: Ecosystem brand governance
description: Official names, identities, canonical assets, palettes, and prohibited substitutions across the SPM-Kit ecosystem.
---

# Ecosystem brand governance

Consistency means coherent relationships, not identical appearances. The site
supplies the grid, typography, evidence vocabulary and interaction behavior;
each repository keeps its own canonical banner and role.

## Parent and child hierarchy

The public relationship is always:

**Pharos Project → SPM-Kit ecosystem → five specialized components.**

Pharos supplies the parent seal, warm editorial frame and project signature.
SPM-Kit is the AFM/SPM instrument inside that portfolio. SPM-Kit Core, Fathom,
Data Hunter, Phantoms and Validation are component identities inside the
instrument; none replaces the parent seal or claims ownership of the ecosystem.

The persistent header therefore pairs the canonical Pharos lighthouse with the
text **SPM-Kit ecosystem**, an **Instrumentation** label and a stable return link
to Pharos. The global favicon is the Pharos mark. Fathom artwork is reserved for
Fathom pages, its canonical banner and the desktop application.

## Shared portal tokens

| Role | Dark | Light | Rule |
|---|---|---|---|
| Canvas | `#0A0908` | `#F4F0E7` | warm night / warm paper |
| Surface | `#15110D` | `#FFFDF8` | content and navigation surfaces |
| Raised surface | `#1C1712` | `#EBE3D6` | code, controls and quiet emphasis |
| Text | `#EFE7D8` | `#201A15` | primary reading color |
| Muted text | `#C8BBA8` | `#5F5143` | secondary copy |
| Rule | `#2A2118` | `#D8CDBD` | restrained dividers and borders |
| Primary action | `#F5A72C` | `#8A4B00` | links, focus and primary actions |
| SPM beam | `#FB923C` | `#B74F13` | SPM-Kit instrument accent |
| Signal teal | `#2DD4BF` | `#0F766E` | data signal and Fathom identity only |

The source of truth is [`tokens.css`](../stylesheets/tokens.css). Material theme
variables, the documentation components and the PDF reader consume those
semantic roles instead of declaring parallel palettes.

## Typography and composition

- **Fraunces** is the selective display face for major editorial headings.
- **Inter** is the reading and interface face.
- **IBM Plex Mono** is reserved for status, evidence labels, utilities and data.
- All fonts are vendored, licensed and loaded with `font-display: swap`.
- Dividers and open editorial groups are preferred over a wall of rounded cards.
- Buttons use one of three explicit roles: primary, secondary or quiet.
- Status never depends on color alone; every state has a visible text label.

The status grammar has seven independent semantic roles: **success** for a
declared passing check, **warning** for caution, **error** for a failed check,
**informational** for non-evaluative context, **blocked** for work that cannot
proceed, **experimental** for alpha or research-stage capabilities, and
**neutral** for unevaluated state. Each role has a distinct dark/light token and
text label. Component accents and scientific signal colors are never substituted
for these status tokens.

The footer uses the canonical Pharos signature:

```text
┌─
│ Pharos Project
│ José Labarca Baeza
└─ USM · Valparaíso · Chile
```

| Official name | Repository | Public subtitle | Banner source | Mark/logo | Accent | Preferred description |
|---|---|---|---|---|---|---|
| SPM-Kit Core | `kegouro/spmkit` | Numerical engine | `docs/images/brand/spmkit_banner_final.png` | Core square artwork remains archival; Fathom mark is not substituted for Core | Pharos amber `#F5A72C` | Headless numerical engine, Python API, CLI and plugin contracts for AFM/SPM analysis |
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
- Use Pharos night/paper and amber as the common site frame; retain each companion's banner palette locally.
- Reserve signal teal for Fathom identity and scientific data, never global ownership or primary portal chrome.
- Preserve intrinsic image dimensions, meaningful alt text and local copies.
- Label synthetic screenshots and generated phantom plots.

## Prohibited substitutions

- Fathom banner presented as SPM-Kit Core;
- Fathom mark used as the portal logo or global favicon;
- SPM-Kit presented as independent from or institutionally owned by Pharos;
- Core described as a GUI or Fathom described as independent numerical software;
- Data Hunter presented as a validator/certifier;
- Phantoms presented as physical evidence or a complete microscope simulator;
- Validation presented as internal unit tests or every PASS as universal validity;
- acknowledgements converted into software authorship, institutional ownership or endorsement;
- the SPM Lab or Universidad Técnica Federico Santa María presented as software owner;
- remote raw-GitHub hotlinks used as production assets.

## Asset audit

The canonical parent assets are exact, hash-recorded copies from
`kegouro.github.io/assets/`; their provenance is recorded in
[`assets/brand/README.md`](../assets/brand/README.md). The global mark is not a
claim that every component shares one software package or one authorship line.

The [machine-readable manifest](../assets/ecosystem/assets-manifest.yml) records
the audited commits, every discovered visual asset, true formats, dimensions,
bytes, transparency, use, duplicates, obsolete candidates, text concerns and
SHA-256. [Read the selection rationale](../assets/ecosystem/ASSETS.md).

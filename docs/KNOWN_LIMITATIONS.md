---
description: Current scientific, format, distribution, and interface limits of SPM-Kit and Fathom.
---

# Known limitations

SPM-Kit is alpha software. Its strongest current public evidence is deliberately
narrower than its feature list. This page collects the practical boundaries a
researcher should check before treating an output as scientific evidence.

## Scientific scope

- No capability currently carries a general `LEVEL 4 — PHYSICALLY_VALIDATED`
  or `LEVEL 5 — REPRODUCIBILITY_VALIDATED` claim.
- The retained Gwyddion campaigns cover Sa, Sq, and Sz under declared
  preprocessing, matrix, version, and tolerance conditions. They do not prove
  universal equivalence with Gwyddion.
- Contact-mechanics, chain, relaxation, and force-volume recovery evidence is
  synthetic. Tip shape, spring constant, sensitivity, contact point, adhesion,
  sample geometry, and fit window remain experiment-specific responsibilities.
- KPFM, spectral, grain, and resonance utilities have software evidence but no
  broad public physical-reference campaign.

## File and metadata scope

- Reader support is variant-specific, not a promise that every file sharing an
  extension will load correctly.
- Nanoscope `.spm` evidence covers six demonstrated files and was affected by a
  documented pre-freeze unblinding incident.
- NanoSurf `.nid` comparisons include selected laboratory-context files, but
  the private instrument corpus is not distributed.
- Optional adapters inherit behavior from their installed dependency versions.
- Instrument metadata is preserved when available; its presence does not prove
  calibration, traceability, or scientific suitability.

## Distribution and interface scope

- The current source tree is `0.1.5.dev0`, the latest GitHub release is `0.1.4`,
  and PyPI currently serves `0.1.2`. Choose an installation source explicitly.
- Fathom depends on Qt and platform graphics behavior. Offscreen GUI tests do
  not establish identical behavior on every desktop.
- The CLI and public Python API are the automation contracts. GUI labels and
  layouts may evolve during alpha releases.

## Evidence handling

Data Hunter records candidates; it does not certify them. Phantoms provide
declared truth; they are not physical references. Validation records campaign
outcomes; a successful run only supports the frozen claim and scope written in
that campaign.

For capability-level detail, use the [scientific status matrix](scientific-status.md),
the [format matrix](FILE_FORMATS.md), and the [retained campaign record](validation/index.md).

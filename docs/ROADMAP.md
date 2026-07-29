# Roadmap

The roadmap follows the evidence hierarchy: scientific correctness, evidence
integrity, authorship accuracy, reproducibility, traceability, safety, usability,
and visual polish.

## Current alpha baseline

- SPM-Kit core, CLI, and Fathom share one numerical implementation.
- Image metrology, force spectroscopy, KPFM, spectral, resonance, reporting,
  and extension paths are implemented with different evidence maturity.
- Selected Sa/Sq/Sz claims have `LEVEL 3` external comparison evidence.
- The limited Nanoscope III `.spm` path has `LEVEL 2` evidence for six
  demonstrated files and remains partial.
- All other maturity claims are listed in [Scientific status](scientific-status.md).

## Evidence priorities

1. Acquire redistributable, independently curated reader fixtures across
   vendors, versions, channels, orientations, and operating systems.
2. Freeze independent force-spectroscopy comparisons with explicit calibration,
   preprocessing, models, fitting windows, tolerances, and uncertainty.
3. Run a genuinely blind holdout campaign that has not been exposed during
   implementation or preflight.
4. Add calibrated physical-reference campaigns without promoting narrow
   experimental evidence into universal validity.
5. Obtain independent reproduction of a frozen public campaign.

## Engineering priorities

- stabilize the public API and project format before 1.0;
- make optional-reader failures and capability discovery clearer;
- expand packaging and GUI smoke coverage across macOS, Linux, and Windows;
- automate drift checks for package version, citation DOI, author, and public links;
- keep Fathom presentation code thin over `spmkit.core`.

## Community priorities

- small format fixtures with explicit redistribution rights;
- independently generated Gwyddion/TopoStats comparisons;
- AFMReader interoperability work that respects project licenses and APIs;
- failed cases and negative evidence, not only successful examples.

Roadmap entries are intentions (`LEVEL 0 — CLAIMED`) until implementation and
evidence are preserved.

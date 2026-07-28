# SPM-Kit Data Hunter

<p align="center">
  <img src="../../assets/ecosystem/data-hunter-banner.png" alt="spmkit-data-hunter banner" width="100%">
</p>

**Discover, catalog, and triage public AFM/SPM datasets.**

Data Hunter searches public scientific repositories (Zenodo, Figshare,
DataCite) for AFM/SPM datasets, catalogs them with structural metadata, and
classifies their scientific utility for validation campaigns.

## What it does

- Searches public APIs (no scraping)
- Persistent SQLite catalog with file inventories
- Evidence-chain scoring (Gold/Silver/Bronze)
- Utility classification: `benchmark_ready`, `reader_fixture`, `crosscheck_candidate`, etc.
- Durable campaigns with page-granular checkpoints
- Selective downloads with checksum verification

## What it does not do

- Not a validator (discovery ≠ validation)
- Not an AFM analyzer
- Not a claim of dataset correctness
- "Gold" means the evidence chain *appears* complete, not that the data is correct

## Links

- **Repository:** [github.com/kegouro/spmkit-data-hunter](https://github.com/kegouro/spmkit-data-hunter)
- **Citation:** [CITATION.cff](https://github.com/kegouro/spmkit-data-hunter/blob/main/CITATION.cff)

---

[:material-arrow-left: Phantoms](phantoms.md) · [:material-arrow-right: Validation](validation.md)

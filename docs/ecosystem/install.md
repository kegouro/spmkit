---
title: Ecosystem installation matrix
description: Verified package names, Python requirements, install sources, entry points, and relationships for every SPM-Kit ecosystem component.
---

# Ecosystem installation matrix

The repositories are separate on purpose. `pip install spmkit` installs neither
Data Hunter, Phantoms nor Validation.

| Component | Package / Python | Current distribution status | Install | Launch or verify | Use when |
|---|---|---|---|---|---|
| SPM-Kit Core | `spmkit` / Python ≥3.11 | PyPI `0.1.2`; GitHub release `0.1.4`; source `0.1.5.dev0` | `python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"` | `spmkit --version`; `spmkit --help` | Python, CLI, batch, notebooks, CI, HPC |
| Fathom | `spmkit[gui]` / Python ≥3.11 | bundled with the chosen SPM-Kit version | `python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"` | `spmkit gui --help` | interactive inspection and operation |
| Data Hunter | `spmkit-data-hunter` / Python ≥3.11 | source/development; not on PyPI | clone, then `python -m pip install -e ".[dev]"` | `spmkit-data-hunter --self-test`; `spmkit-data-hunter doctor` | public evidence discovery and triage |
| Phantoms | `spmkit-phantoms` / Python ≥3.10 | source/development; not on PyPI | clone, then `python -m pip install -e ".[dev]"` | `spmkit-phantoms --help` | deterministic analytical truth |
| Validation | `spmkit-validation` / Python ≥3.10 | source/development; not on PyPI | clone, then `python -m pip install -e .` | `spmkit-validation --help` | external campaign execution/evidence |

## Core source choices

### Latest GitHub tag

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"
spmkit --version
```

### Current documentation source

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"
spmkit --version
```

Pin a commit instead of `main` for a retained scientific workflow.

### Editable contributor environment

```bash
git clone https://github.com/kegouro/spmkit.git
cd spmkit
python -m pip install -e ".[dev,gui,hdf5,test-gui]"
pytest --collect-only -q --no-cov
```

## Companion development installs

```bash
git clone https://github.com/kegouro/spmkit-data-hunter.git
git clone https://github.com/kegouro/spmkit-phantoms.git
git clone https://github.com/kegouro/spmkit-validation.git

python -m pip install -e "./spmkit-data-hunter[dev]"
python -m pip install -e "./spmkit-phantoms[dev]"
python -m pip install -e ./spmkit-validation
```

Synthetic Validation campaigns import Phantoms in the current source, so install
both in the same validation environment. The campaign invokes SPM-Kit as an
external executable; use `--spmkit /absolute/path/to/spmkit` or ensure the
intended executable is first on `PATH`.

## Core extras

| Extra | Purpose |
|---|---|
| `gui` | Fathom workspace |
| `hdf5` | HDF5 support |
| `gwy` | Gwyddion `.gwy` support |
| `nanosurf` | optional `.nhf` reader dependency |
| `afm` | `afmformats` adapter |
| `jpk` | JPK TIFF support |
| `grains` | SciPy grain analysis |
| `parallel` | joblib force-volume backend |
| `pandas` | DataFrame exports |
| `viz` | scientific figures |
| `report` | report dependencies |
| `all` | all runtime extras |

## Verification boundaries

`--help`, import checks and offline self-tests verify installation. They do not
validate a dataset, instrument calibration or scientific model. A faster result
with weaker provenance is not an optimization.

[Core installation detail](../getting-started/installation.md) ·
[Artifact contracts](contracts.md)

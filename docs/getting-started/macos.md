# macOS and Linux from a clean clone

This consolidation was executed on Linux x86_64 with Python 3.12.13. macOS,
Apple Silicon, native display behavior and instrument access remain untested.
Python >=3.11 remains the package minimum; use 3.12 for the frozen evidence
constraints below. No ROOT, MATLAB, local sibling repository or Gwyddion
installation is required to run the numerical engine or Fathom.

## Install on Mac

Install Python 3.12 and Git (for example `brew install python@3.12 git`), then:

```bash
git clone https://github.com/kegouro/spmkit.git
cd spmkit
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -c requirements-reproducible.txt -e ".[gui,hdf5,gwy,jpk]"
spmkit --version
spmkit --help
python -c "from spmkit.core.analysis import roughness; print('Core OK')"
spmkit gui
```

For a headless installation use `-e .` instead of GUI extras. Qt is optional;
core imports do not load PyQt6. Qt <6.12 currently avoids incompatible new
stubs observed during the clean development type check. This is a temporary
compatibility bound, not a change to the Python minimum.

## Reproducible development

```bash
python -m pip install -c requirements-reproducible.txt -e ".[dev,gui,test-gui,hdf5,gwy,jpk,docs]"
python -m pip freeze > environment.local.txt
ruff check src tests
black --check src tests
mypy src
pytest --ignore=tests/gui --ignore=tests/e2e/gui
QT_QPA_PLATFORM=offscreen bash scripts/run_gui_tests.sh
python -m pip install build
python -m build
```

Record `git rev-parse HEAD` with exported results. `spmkit analyze INPUT`
writes a basename-only SHA-256 execution manifest with selection parameters,
versions and warnings beside CSV/JSON results. These records establish software
provenance, not instrument calibration or physical validation.

Companion packages stay independent. Frozen Gwyddion executable campaigns need
their own platform-specific reference build; archived Linux ELF helpers cannot
run on macOS. See [consolidation](../ecosystem/consolidation-20261121.md).

# Installation

SPM-Kit requires Python 3.11 or newer. The numerical Core is headless; Fathom
adds PyQt6, pyqtgraph and plotting dependencies through the `gui` extra.

## Choose a version deliberately

| Source | Version on 29 July 2026 | Command | Use when |
|---|---|---|---|
| PyPI | `0.1.2` | `python -m pip install spmkit` | You specifically need the older published wheel |
| GitHub release | `0.1.4` | `python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"` | You need the latest tagged source release |
| Current development | `0.1.5.dev0` | `python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"` | You need the behavior documented on this development site |

PyPI lags the GitHub release. A bare `pip install spmkit` does not currently
produce the release or development versions documented here.

## Core and CLI

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "spmkit @ git+https://github.com/kegouro/spmkit@v0.1.4"
spmkit --version
spmkit --help
```

On Windows PowerShell activate with `.venv\Scripts\Activate.ps1`.

## Fathom

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"
python -c "from spmkit.gui.app_workspace import build_workspace; print('Fathom import OK')"
spmkit gui
```

Fathom requires a display. `QT_QPA_PLATFORM=offscreen` is for automated GUI
tests, not a useful interactive session.

## Optional extras

| Extra | Adds |
|---|---|
| `gui` | Fathom: PyQt6, pyqtgraph and visualization support |
| `gwy` | `.gwy` read/write through `gwyfile` |
| `nanosurf` | `.nhf` support through NSFopen |
| `afm` | optional long-tail readers through `afmformats` |
| `jpk` | JPK TIFF support through `tifffile` |
| `hdf5` | HDF5 export/read dependencies |
| `grains` | SciPy-backed grain analysis |
| `viz` | publication figures and scientific colormaps |
| `report` | HTML/PDF reporting dependencies |
| `all` | all runtime extras listed in `pyproject.toml` |

## Editable development install

```bash
git clone https://github.com/kegouro/spmkit.git
cd spmkit
python -m pip install -e ".[dev,gui,hdf5,test-gui]"
spmkit --version
pytest --collect-only -q --no-cov
```

The companion repositories are separate packages. See the
[ecosystem installation matrix](../ecosystem/install.md) before attempting an
evidence-discovery or validation workflow.

## Verify the numerical boundary

```bash
python - <<'PY'
from spmkit.core.analysis.roughness import statistics
from spmkit.core.models import SPMChannel
import numpy as np

channel = SPMChannel("Height", np.array([[0.0, 1.0], [2.0, 3.0]]), "nm", 1e-6, 1e-6)
result = statistics(channel)
print(result.Sa, result.Sq, result.Sz, result.unit)
PY
```

This verifies import and a public numerical function without requiring an
instrument file. It does not validate your instrument calibration or establish
physical metrological traceability.

[:material-arrow-right: First analysis](first-analysis.md)

---
description: Choose an installation source, run a first SPM-Kit analysis, or open the Fathom workspace.
---

# Getting started

SPM-Kit separates numerical work from presentation. Use the Python API or CLI
for scripts, pipelines, and reproducible runs; use Fathom when visual inspection
and interactive region selection are part of the work.

## Choose a path

| Goal | Start here | First successful result |
|---|---|---|
| Install a specific release or development state | [Installation](getting-started/installation.md) | `spmkit --version` and `spmkit --help` succeed |
| Analyze a file or an in-memory surface | [First analysis](getting-started/first-analysis.md) | roughness values with declared units and preprocessing |
| Explore data interactively | [Fathom quick start](getting-started/fathom-quick-start.md) | a channel is loaded into the `Imagen` perspective |
| Connect discovery, synthetic truth, and validation | [Example workflows](ecosystem/workflows/index.md) | a provenance-preserving artifact chain |

## Requirements

- Python 3.11 or newer;
- `pip` or `uv`;
- the `gui` extra only for Fathom;
- format-specific extras only where the [format matrix](FILE_FORMATS.md) says
  they are required.

## Thirty-second source install

The site documents the `0.1.5.dev0` source tree. Install that state explicitly:

```bash
python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"
spmkit --version
spmkit --help
```

PyPI currently serves `0.1.2`; the latest GitHub release is `0.1.4`. The
[installation matrix](getting-started/installation.md) explains the difference.

## Scientific checkpoint

Loading a file is not validation. Before using a result in a scientific claim,
record the input checksum, reader path, channel, units, preprocessing,
parameters, software version, and output checksum. Then match the claim to the
[scientific status matrix](scientific-status.md).

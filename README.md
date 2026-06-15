# spmkit

[![CI](https://github.com/spm-lab-utfsm/spmkit/actions/workflows/ci.yml/badge.svg)](https://github.com/spm-lab-utfsm/spmkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/spmkit.svg)](https://pypi.org/project/spmkit/)
[![Python](https://img.shields.io/pypi/pyversions/spmkit.svg)](https://pypi.org/project/spmkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Analizador **open-source** de datos de microscopía de sonda de barrido (SPM),
con foco en **AFM** y **KPFM**. Desarrollado en el **SPM Lab de la UTFSM**.

Lee formatos NanoSurf (`.nid`, `.nhf`), calcula rugosidad, perfiles de línea y
estadísticas KPFM (CPD / función de trabajo), y exporta a formatos abiertos
(CSV, HDF5, JSON). Incluye CLI y una GUI científica (PyQt6 + pyqtgraph).

## Arquitectura

Separación estricta en tres capas. CLI y GUI **solo** usan la API pública del
`core`; nunca tocan parsers ni implementan análisis.

```
┌───────────────┐     ┌───────────────┐
│   cli/        │     │   gui/        │   ← capas de presentación
│ (typer+rich)  │     │ (PyQt6+pg)    │
└───────┬───────┘     └───────┬───────┘
        │   importan funciones del core   │
        └───────────────┬─────────────────┘
                        ▼
        ┌───────────────────────────────┐
        │            core/              │   ← puro Python, sin UI
        │  io · models · analysis · export │
        └───────────────────────────────┘
                        ▲
        .nid / .nhf  ───┘  (archivos del instrumento)
```

## Instalación

```bash
# Recomendado: con uv
uv pip install spmkit            # núcleo + CLI
uv pip install "spmkit[gui]"     # + interfaz gráfica (PyQt6, incluye viz)
uv pip install "spmkit[viz]"     # + figuras de publicación (matplotlib, colormaps, scale bar)
uv pip install "spmkit[gwy]"     # + interop Gwyddion (.gwy)
uv pip install "spmkit[hdf5]"    # + lectura/exportación HDF5
uv pip install "spmkit[report]"  # + reportes HTML/PDF
uv pip install "spmkit[nanosurf]"# + lector .nhf validado (NSFopen)
uv pip install "spmkit[all]"     # todo

# Desarrollo (desde el repo)
uv pip install -e ".[dev,gui,hdf5,gwy,report]"
pre-commit install
```

> También funciona con `pip` clásico (`pip install spmkit`). El build backend es
> `hatchling`, moderno y compatible.

## Uso rápido

### CLI

```bash
spmkit info scan.nid                          # metadatos y canales
spmkit roughness scan.nid -c Z-Axis           # rugosidad (ISO 25178)
spmkit analyze scan.nid -o ./results/         # pipeline completo → CSV+JSON
spmkit nanomech spec.nid --tip-radius 10e-9   # ajuste Hertz → módulo de Young
spmkit batch ./carpeta/ -o resumen.csv        # procesa una carpeta completa
spmkit figure scan.nid -o fig.svg --colormap batlow   # figura de publicación
spmkit convert scan.nid scan.gwy              # convierte a Gwyddion (.gwy)
spmkit gui                                     # interfaz gráfica
```

### Como librería

```python
from spmkit import load
from spmkit.core.analysis import leveling, roughness, profiles, kpfm

data = load("scan.nid")
print(data.names)                       # ['Z-Axis', 'CPD', 'Amplitude', ...]

ch    = data["Z-Axis"]
flat  = leveling.plane_fit(ch)          # corrige inclinación
stats = roughness.statistics(flat)      # Sa, Sq, Sz, Ssk, Sku
print(stats.Sq, stats.unit)

line  = profiles.line(flat, (0, 0), (100, 100))   # perfil de línea
cpd   = kpfm.statistics(data["CPD"], tip_work_function=5.0)
```

## Capacidades

- **Lectura**: NanoSurf `.nid` (validado), `.nhf` (HDF5) y Gwyddion `.gwy`.
- **Análisis**: rugosidad ISO 25178, nivelación, perfiles, KPFM (CPD/función de
  trabajo) y **nanomecánica** (curvas fuerza-distancia, Hertz/Sneddon → módulo
  de Young, punto de contacto, adhesión).
- **Interop Gwyddion**: lee/escribe `.gwy` (pure-Python) y abre el archivo en
  Gwyddion con un clic.
- **Figuras de publicación**: editor WYSIWYG (título, ejes, colormaps
  científicos, barra de escala, anotaciones arrastrables) → PNG/SVG/PDF.
- **Quality of life**: procesamiento por lotes, reportes HTML/PDF, archivos
  recientes, drag & drop, tema claro/oscuro.

## Formatos soportados

| Formato | Extensión | Estado |
|---------|-----------|--------|
| NanoSurf clásico | `.nid` | ✅ Lectura completa (validado) |
| NanoSurf HDF5 | `.nhf` | 🧪 Experimental (`[hdf5]` o `[nanosurf]`) |
| Gwyddion | `.gwy` | ✅ Lectura y escritura (`[gwy]`) |
| Exportación | `.csv`, `.json`, `.h5`, `.png/.svg/.pdf` | ✅ |

## Desarrollo

```bash
pytest                  # tests + cobertura
ruff check src tests    # lint
black src tests         # formato
mypy src                # tipos
```

## Citación

Si usas spmkit en tu investigación, cítalo según [`CITATION.cff`](CITATION.cff).

## Licencia

MIT © 2026 SPM Lab UTFSM — Prof. Tomás Corrales, José Labarca.

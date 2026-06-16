# Primeros pasos

## Requisitos

- **Python ≥ 3.11**
- pip o [uv](https://github.com/astral-sh/uv)

---

## Instalación

### Núcleo + CLI

```bash
pip install spmkit
```

El paquete base incluye la CLI (`spmkit`) y el core de análisis (sin dependencias pesadas).

### Con interfaz gráfica

```bash
pip install "spmkit[gui]"
```

Añade PyQt6, pyqtgraph y matplotlib (necesario para las 7 pestañas de la GUI).

### Extras disponibles

| Extra | Qué agrega |
|-------|-----------|
| `gui` | Interfaz gráfica (PyQt6 + pyqtgraph) |
| `viz` | Figuras de publicación (matplotlib, cmcrameri, scale bar) |
| `gwy` | Interoperabilidad con Gwyddion (`.gwy`) |
| `hdf5` | Lectura / exportación HDF5 |
| `grains` | Detección de granos y partículas (scipy) |
| `report` | Reportes HTML/PDF (Jinja2) |
| `nanosurf` | Lector `.nhf` validado (NSFopen) |

Instalar varios extras:

```bash
pip install "spmkit[gui,gwy,hdf5]"
```

Instalar todo:

```bash
pip install "spmkit[all]"
```

### Desde el repositorio (desarrollo)

```bash
pip install "git+https://github.com/kegouro/spmkit#egg=spmkit[gui]"
```

---

## Verificación

```bash
spmkit --version
```

Resultado esperado:

```
spmkit 0.1.0
```

---

## Primer uso — CLI

### Ver metadatos de un archivo

```bash
spmkit info scan.nid
```

Muestra los canales disponibles, sus dimensiones y unidades.

### Calcular rugosidad

```bash
spmkit roughness scan.nid -c Z-Axis
```

Parámetros ISO 25178: Sa, Sq, Sz, Ssk, Sku.

### Pipeline completo

```bash
spmkit analyze scan.nid --output ./results
```

Genera `results/scan_roughness.csv`, `results/scan_roughness.json` y (si hay canal CPD) los archivos KPFM equivalentes.

### Abrir la GUI

```bash
spmkit gui
```

!!! note "Requisito extra"
    La GUI requiere el extra `gui`. Si ves un error, instala con `pip install "spmkit[gui]"`.

---

## Primer uso — como librería Python

```python
from spmkit import load
from spmkit.core.analysis import leveling, roughness, kpfm

# Cargar un archivo .nid
data = load("scan.nid")

# Ver canales disponibles
print(data.names)

# Seleccionar canal y nivelar
ch = data["Z-Axis"]
flat = leveling.plane_fit(ch)   # corrige inclinación de plano

# Calcular rugosidad
stats = roughness.statistics(flat)
print(f"Sa = {stats.sa:.4g} {stats.unit}")
print(f"Sq = {stats.sq:.4g} {stats.unit}")

# Análisis KPFM (si el archivo contiene canal CPD)
cpd = kpfm.statistics(data["CPD"], tip_work_function=5.0)
print(f"CPD medio = {cpd.mean_cpd:.4g} V")
```

---

## Siguiente paso

- Explora todos los comandos CLI en la [Referencia CLI](cli.md).
- Conoce la GUI en la [Guía de usuario](user-guide.md).
- Revisa la [API Python](api.md) para integraciones avanzadas.

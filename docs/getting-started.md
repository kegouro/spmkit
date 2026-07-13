# Primeros pasos

## Requisitos

- **Python 3.11–3.12**
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

Añade PyQt6, pyqtgraph y matplotlib para abrir Fathom, el workspace organizado por
perspectivas de análisis.

### Extras disponibles

| Extra | Qué agrega |
|-------|-----------|
| `gui` | Interfaz gráfica (PyQt6 + pyqtgraph) |
| `viz` | Figuras de publicación (matplotlib, cmcrameri, scale bar) |
| `gwy` | Interoperabilidad con Gwyddion (`.gwy`) |
| `hdf5` | Lectura experimental `.nhf` y exportación HDF5 (h5py) |
| `grains` | Detección de granos y partículas (scipy) |
| `report` | Reportes HTML/PDF (Jinja2) |

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
spmkit 0.1.4
```

---

## Primer uso — journey de imagen

Para recorrer el flujo completo usa un archivo `.gwy` con topografía y, si quieres KPFM,
un canal CPD. Instala `gwy` para leerlo, `viz` para exportar la figura y `gui` para abrirlo
en Fathom:

```bash
pip install "spmkit[gwy,viz,gui]"
```

Primero inspecciona los nombres, direcciones, grupos, formas y unidades disponibles:

```bash
spmkit info scan.gwy
```

Luego calcula estadísticas areales de la topografía nivelada, extrae un perfil entre
coordenadas `(X, Y)` de píxel y ejecuta el análisis de topografía y CPD:

```bash
spmkit roughness scan.gwy --channel Z-Axis --direction forward --level plane
spmkit profile scan.gwy --channel Z-Axis --direction forward \
  --x0 0.5 --y0 0.5 --x1 5.5 --y1 3.5 --n 3 --level plane \
  --output profile.csv
spmkit analyze scan.gwy --output ./results \
  --channel Z-Axis --direction forward \
  --cpd-channel CPD --cpd-direction forward --tip-wf 4.7
```

Las coordenadas del perfil deben quedar dentro de la forma mostrada por `info`. El CSV
resultante tiene las columnas `distance[m]` y `height[unidad del canal]`; `analyze` genera
CSV y JSON separados para rugosidad y, cuando existe el canal seleccionado, KPFM.

Finalmente exporta una figura y abre el mismo archivo en Fathom:

```bash
spmkit figure scan.gwy --channel Z-Axis --direction forward \
  --output topography.png
spmkit gui scan.gwy
```

Si un nombre está duplicado, debes añadir `--direction`; si todavía hay más de una
coincidencia, añade también `--group`. `spmkit info` muestra todos los registros y ambas
columnas para que puedas elegir sin depender del orden del archivo.

`roughness` entrega estadísticas areales como `Sa`, `Sq`, `Sz`, `Sp`, `Sv`, `Ssk` y `Sku`;
este subconjunto no se presenta como cumplimiento integral de ISO 25178.

---

## Primer uso — como librería Python

```python
from spmkit import load
from spmkit.core.analysis import kpfm, leveling, profiles, roughness

data = load("scan.gwy")

# select() exige una coincidencia única
raw = data.select("Z-Axis", direction="forward")
flat = leveling.plane_fit(raw)

profile = profiles.line(flat, (0.5, 0.5), (5.5, 3.5), n=3)
print(profile.distance, profile.height)

stats = roughness.statistics(flat)
print(f"Sa = {stats.Sa:.4g} {stats.unit}")
print(f"Sq = {stats.Sq:.4g} {stats.unit}")

cpd_channel = data.select("CPD", direction="forward")
cpd = kpfm.statistics(cpd_channel, tip_work_function=4.7)
print(f"CPD medio = {cpd.mean:.4g} {cpd.unit}")
print(f"Función de trabajo = {cpd.work_function} {cpd.work_function_unit}")
```

El core conserva los canales raw: la nivelación devuelve un `SPMChannel` nuevo y no modifica
`raw`. Los datos están en la unidad física indicada; los rangos espaciales están en metros.

La convención implementada es `phi_sample = phi_tip - mean(CPD)` al expresar la función de
trabajo en eV y el CPD en V. Si omites `tip_work_function`, `work_function` queda en `None`:
spmkit no inventa una función de trabajo de la punta.

---

## Siguiente paso

- Explora todos los comandos CLI en la [Referencia CLI](cli.md).
- Conoce la GUI en la [Guía de usuario](user-guide.md).
- Revisa la [API Python](api.md) para integraciones avanzadas.

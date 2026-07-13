# API Python

spmkit expone una API pública limpia en `spmkit.core`. La CLI y la GUI solo orquestan — toda la lógica vive aquí.

## Instalación

```bash
pip install spmkit
```

---

## Carga de datos — `spmkit.load`

Punto de entrada principal. Detecta el formato automáticamente.

```python
from spmkit import load

data = load("scan.nid")    # NanoSurf clásico
data = load("scan.nhf")    # NanoSurf HDF5 (lector experimental)
data = load("scan.gwy")    # Gwyddion
```

### `SPMData`

El objeto devuelto por `load()`.

```python
# Ver canales disponibles
print(data.names)          # ['Z-Axis', 'CPD', 'Phase', ...]

# Selección estricta: debe quedar exactamente una coincidencia
ch = data.select("Z-Axis", direction="forward")
ch = data.select("Z-Axis", direction="forward", group="Topography forward")

# Compatibilidad: acceso no estricto por nombre
ch = data.get("Z-Axis")
ch = data["Z-Axis"]

# Metadatos del barrido
print(data.metadata)       # dict con parámetros del instrumento
```

`select(name, direction=..., group=...)` lanza `KeyError` si no encuentra coincidencias y
`ValueError` si encuentra más de una. Es la opción recomendada cuando hay nombres duplicados.

`get(name, direction="forward")` conserva el acceso histórico: busca esa dirección y, si no
existe, devuelve la primera coincidencia por nombre. `data[name]` equivale a `get(name)`;
ninguna de estas dos formas detecta ambigüedad.

### `SPMChannel`

Representa un canal 2D en unidades físicas.

```python
ch = data["Z-Axis"]

ch.data        # numpy.ndarray 2D (shape: rows × cols)
ch.unit        # str, p.ej. "m", "V", "°"
ch.x_range     # float, rango horizontal en metros
ch.y_range     # float, rango vertical en metros
ch.shape       # tuple (rows, cols)
ch.name        # str, nombre del canal
ch.direction   # "forward" | "backward"
ch.group       # str, grupo de origen
ch.metadata    # dict, metadatos crudos del canal
```

---

## Nivelación — `spmkit.core.analysis.leveling`

```python
from spmkit.core.analysis import leveling

# Corrección de plano (elimina inclinación)
flat = leveling.plane_fit(ch)

# Corrección polinómica (orden configurable)
flat = leveling.polynomial(ch, order=2)

# Alineado de filas (corrige deriva línea a línea)
flat = leveling.align_rows(ch)
```

Todas las funciones devuelven un nuevo `SPMChannel` (inmutable).

---

## Rugosidad — `spmkit.core.analysis.roughness`

Estadísticas de rugosidad areal.

```python
from spmkit.core.analysis import roughness

result = roughness.statistics(flat)

result.Sa      # rugosidad media aritmética
result.Sq      # rugosidad RMS
result.Sz      # altura máxima (Sp + |Sv|)
result.Sp      # altura máxima de picos
result.Sv      # profundidad máxima de valles (valor negativo)
result.Ssk     # asimetría (skewness)
result.Sku     # curtosis (kurtosis)
result.unit    # unidad del canal ("m", "nm", …)
result.n_points  # puntos finitos usados

# Convertir a dict
d = result.to_dict()
```

---

## KPFM — `spmkit.core.analysis.kpfm`

Potencial de contacto y función de trabajo.

```python
from spmkit.core.analysis import kpfm

# Estadísticas básicas del canal CPD
cpd_channel = data.select("CPD", direction="forward")
result = kpfm.statistics(cpd_channel)

result.mean           # CPD medio
result.std            # desviación estándar
result.minimum        # mínimo
result.maximum        # máximo
result.contrast       # máximo - mínimo
result.unit           # unidad del canal (debe ser V)
result.work_function  # None: no se proporcionó la función de trabajo de la punta

# Con función de trabajo de la punta (eV)
result = kpfm.statistics(cpd_channel, tip_work_function=4.7)
result.work_function  # función de trabajo de la muestra (eV)
result.work_function_unit  # "eV"
```

La relación implementada es `phi_sample = phi_tip - mean(CPD)`. Sin
`tip_work_function`, el resultado conserva `work_function=None`.

---

## Perfiles — `spmkit.core.analysis.profiles`

```python
from spmkit.core.analysis import profiles

profile = profiles.line(
    ch,
    (0.5, 0.5),  # (columna, fila) inicial en píxeles
    (5.5, 3.5),  # (columna, fila) final en píxeles
    n=3,
)

profile.distance       # ndarray, distancia física
profile.height         # ndarray, valores interpolados del canal
profile.distance_unit  # "m"
profile.unit           # unidad de altura del canal
len(profile)           # número de muestras
```

Ambos extremos deben estar dentro de la imagen. `n=None` elige el número de muestras a
partir de la longitud del segmento en píxeles.

---

## Nanomecánica — `spmkit.core.analysis.mechanics`

Curvas fuerza-distancia, modelos de contacto.

```python
from spmkit.core.analysis import mechanics

# Extraer curvas del canal de espectroscopía
curves = mechanics.extract_curves(data["Deflection"])

# Ajustar modelo de Hertz a una curva
result = mechanics.fit_hertz(
    curves[50],
    tip_radius=10e-9,          # radio de punta (m)
    model="sphere",            # "sphere" | "paraboloid" | "cone"
    spring_constant=0.3,       # N/m (opcional)
)

result.young_modulus   # módulo de Young (Pa)
result.contact_point   # punto de contacto (m)
result.adhesion        # fuerza de adhesión (N)
result.rmse            # error del ajuste

# Mapa de módulo (force-volume)
modulus_map = mechanics.modulus_map(curves, tip_radius=10e-9)
# modulus_map.data → ndarray 2D con E en Pa
```

---

## Resonancia — `spmkit.core.analysis.resonance`

Thermal tuning y sensado de masa.

```python
from spmkit.core.analysis import resonance
from pathlib import Path

# Cargar serie temporal de espectros
files = sorted(Path("./tuning/").glob("*.nid"))
ev = resonance.load_evaporation_series(files, spring_constant=0.3)

ev.time              # ndarray, tiempo (s)
ev.frequency         # ndarray, frecuencia de resonancia (Hz)
ev.mass              # ndarray, masa efectiva (kg)
ev.added_mass        # ndarray, Δm respecto a la primera medida (kg)
ev.evaporation_rate  # ndarray, dm/dt (kg/s)
ev.spring_constant   # float (N/m)
ev.bare_frequency    # float, f₀ sin masa (Hz)

# Ajuste de ley d² (evaporación limitada por difusión)
radii = resonance.droplet_radius(ev.added_mass)
d2 = resonance.fit_d2_law(ev.time, radii)

d2.r0                    # radio inicial (m)
d2.tau                   # tiempo de vida total (s)
d2.rate_constant         # K (m²/s)
d2.r_squared             # R² del ajuste
d2.is_diffusion_limited  # bool
```

---

## Análisis espectral — `spmkit.core.analysis.spectral`

PSD radial, dimensión fractal, longitud de correlación.

```python
from spmkit.core.analysis import spectral

# Dimensión fractal y exponente de Hurst
frac = spectral.fractal_dimension(flat)
frac.fractal_dimension   # D (2 < D < 3 para superficies rugosas)
frac.hurst               # H = 3 - D
frac.psd_slope           # pendiente β del ajuste log-log
frac.r_squared           # bondad del ajuste

# Longitud de correlación
corr_length = spectral.correlation_length(flat)  # metros
```

---

## Granos — `spmkit.core.analysis.grains`

Detección de partículas y estadística de tamaños.

```python
from spmkit.core.analysis import grains

result = grains.detect(
    flat,
    threshold=None,       # None = automático
    min_size=4,           # píxeles mínimos por grano
    relative_height=0.5,  # fracción para umbral auto
)

result.n_grains         # número de granos detectados
result.mean_diameter    # diámetro medio (m)
result.density          # densidad (granos/m²)
result.coverage         # fracción de cobertura (0..1)
result.labels           # ndarray 2D con etiquetas de granos
```

---

## Visualización — `spmkit.core.viz`

Figuras de publicación con colormaps científicos.

```python
from spmkit.core.viz import FigureSpec, save_figure

spec = FigureSpec(
    title="Topografía AFM",
    colormap="gold",                      # valor por defecto
    colorbar_label="Z-Axis (nm)",
)

# Exportar a PNG / SVG / PDF
save_figure(flat, spec, "topografia.png")
save_figure(flat, spec, "topografia.svg")
save_figure(flat, spec, "topografia.pdf")
```

Además de `gold`, hay colormaps de matplotlib y Crameri cuando están instalados, por ejemplo:

`batlow`, `tokyo`, `oslo`, `vik`, `davos`, `hawaii`, `lapaz`, `roma`, `turku`, `acton`

---

## Exportación — `spmkit.core.export`

```python
from spmkit.core.export import to_csv, to_json, to_hdf5

# Exportar resultados de rugosidad
to_csv(roughness_result, "roughness.csv")
to_json(roughness_result, "roughness.json")

# Exportar un perfil: distance[m],height[unidad]
to_csv(profile, "profile.csv")

# Exportar datos completos a HDF5
to_hdf5(data, "scan.h5")
```

---

## Conversión de formatos — `spmkit.core.io`

```python
from spmkit.core.io import save_gwy

# Guardar como Gwyddion (.gwy)
save_gwy(data, "scan.gwy")
```

---

## Procesamiento por lotes — `spmkit.core.batch`

```python
from spmkit.core import batch
from pathlib import Path

# Encontrar archivos SPM en una carpeta
files = batch.find_files(Path("./medidas/"))

# Procesar todos
result = batch.process(files, channel="Z-Axis")

result.n_ok        # archivos procesados con éxito
result.n_failed    # archivos con error
result.to_csv(Path("summary.csv"))
```

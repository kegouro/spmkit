# Espectroscopía de fuerza (curvas de fuerza)

spmkit analiza curvas de fuerza (force-distance) de instrumentos **JPK/Bruker**
(`.jpk-force`) y **NanoSurf** (force-volume en `.nid`), con un pipeline reproducible
que reemplaza el análisis de Nanosurf ANA y JPK Data Processing.

## Flujo

```
cargar → calibrar → detectar contacto → ajustar elasticidad → mapa/batch → exportar
```

Cada análisis se describe con un **Recipe** (YAML), de modo que es reproducible y
compartible. Ver ejemplos en `examples/recipes/`.

## Línea de comandos

Ajustar una curva individual (módulo, R², adhesión, disipación):

```bash
spmkit forcecurve muestra.jpk-force --model dmt --tip-radius 2e-8
```

Analizar un force-volume y guardar el mapa de propiedades como figura:

```bash
spmkit forcemap muestra.nid --figure mapas.png --parallel
```

Procesar por lotes una carpeta completa con una receta reproducible:

```bash
spmkit fbatch ./curvas --recipe examples/recipes/nanoindentation.yaml -o resumen.csv
```

## API de Python (scriptable, reproducible)

```python
from spmkit.core.io import load_jpk_force, load_nid_force
from spmkit.core.analysis.forcevolume import analyze_volume
from spmkit.core.pipeline import Recipe, Step, run

# Una curva JPK
curve = load_jpk_force("muestra.jpk-force")
recipe = Recipe(steps=(
    Step(op="find_contact_point"),
    Step(op="fit_elasticity", params={"model": "sphere", "tip_radius": 1e-8},
         condition="contact_detected"),
))
_, ctx = run(recipe, curve)
print(ctx["young_modulus"], ctx["r_squared"], ctx["adhesion"])

# Un force-volume NanoSurf → mapas de propiedades
volume = load_nid_force("muestra.nid")
result = analyze_volume(volume, recipe, parallel=True)
print(result.stats("young_modulus"))          # media, mediana, σ, mín, máx
emap = result.maps["young_modulus"]           # arreglo 2D (grid_shape)
```

## Recipes (YAML)

Una receta es una lista ordenada de pasos. Cada paso tiene `op`, `params` opcionales
y una `condition` opcional (evaluada de forma **segura**, sin `eval()`):

```yaml
name: mi_analisis
steps:
  - op: calibrate
  - op: find_contact_point
  - op: fit_elasticity
    params: {model: dmt, tip_radius: 2.0e-8}
    condition: contact_detected
```

Operaciones disponibles: `calibrate`, `find_contact_point`, `fit_elasticity`.
Modelos de contacto: `sphere`, `paraboloid`, `cone`, `dmt`.

## Modelos y magnitudes

- **Módulo de Young** con incertidumbre 1σ (y Monte Carlo que propaga InVOLS y k).
- **Adhesión** (pull-off) y **energía de disipación** (histéresis approach/retract).
- **R²** de cada ajuste; los mapas incluyen módulo, adhesión, disipación, R² y contacto.

## Notas de calibración

- Los `.jpk-force` traen la calibración (InVOLS, constante de resorte) en sus
  metadatos y se aplican automáticamente.
- Para `.nid` con la separación punta-muestra saturada, el ajuste usa la altura del
  piezo (módulo "aparente"); ver `docs/design/FORCE_SPECTROSCOPY.md` §18.

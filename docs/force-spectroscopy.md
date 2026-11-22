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

## Medición de posibles escalones de fuerza

Para comprobar una anotación en una curva, conservar el archivo nativo y anotar
la rama, el ciclo y el índice de la primera muestra posterior al posible cambio.
La definición operativa de esta medición es un salto **vertical de fuerza a una
misma altura del piezo**. Confirmar primero los ejes y el modo de adquisición.
Un desplazamiento a fuerza constante requiere otra magnitud y otro método.

Desde la raíz del repositorio se puede ejecutar este ejemplo con el archivo
NanoSurf de referencia. Su posición se eligió para comprobar la lectura y el
formato de salida. La anotación carece de interpretación física.

```sh
spmkit force-steps examples/recipes/force-step-annotations.csv > medidas.jsonl
```

Las rutas del CSV son relativas a la tabla. Los índices de curva, ciclo y
muestra comienzan en cero. Para una frontera `b` y ventana `w`, se ajustan por
mínimos cuadrados dos rectas independientes de fuerza frente a altura, sobre
`[b-w, b)` y `[b, b+w)` en orden de adquisición. Se evalúan en el punto medio
entre las alturas de las muestras `b-1` y `b`. El resultado es la fuerza
posterior menos la anterior, en N. La salida incluye altura en m, pendientes en
N/m, residuales RMS en N, identificación del original por SHA-256, versión del
método y revisión Git cuando está disponible. Se requiere fuerza calibrada,
al menos tres puntos por lado y altura estrictamente monótona en la ventana.
Una rama con una inversión local requiere revisión. El RMS describe el ajuste.
La incertidumbre experimental requiere además caracterizar calibración, ruido
correlacionado y selección de la frontera.

El lote aplica el mismo cálculo a cada fila. Conserva las anotaciones rechazadas
con su motivo, procesa las siguientes y devuelve código 1 si hubo rechazos.
El lote mecánico `fbatch` exporta por separado el número de valores finitos que
contribuyeron a cada propiedad, el hash del archivo y la receta. `n_ok` cuenta
curvas cuyo pipeline terminó, incluso si una condición de la receta omitió
un ajuste.

### Evidencia y límites del piloto

Los ensayos reproducibles están en `tests/core/test_annotated_force_steps.py`.
Incluyen rampas ascendentes y descendentes con saltos de signo conocido y con
salto cero, compatibilidad entre procesamiento individual y lote, y rechazo de
voltios como fuerza calibrada. Para un salto inyectado de 2 nN, frontera
conocida y diez muestras por lado, 512 simulaciones con semilla 20261122 y
ruido marginal de 0,1 nN dieron los siguientes errores de amplitud.

| Ruido | Sesgo (nN) | Raíz del error cuadrático medio (nN) |
| --- | ---: | ---: |
| Gaussiano blanco | +0,00036 | 0,0858 |
| Gaussiano AR(1), correlación 0,8 | +0,00304 | 0,0909 |

La prueba compara la dispersión con la predicción independiente obtenida a
partir de la matriz de covarianza y el contraste lineal. Las cifras son
condicionales a conocer la frontera y a la linealidad local. Buscar primero el
salto más llamativo cambia la distribución del error. La correlación temporal
también importa al evaluar detectores de escalones.
[Estudio de detección bajo ruido correlacionado](https://doi.org/10.1371/journal.pone.0059279)

### Piloto experimental con liquid marbles

1. Recuperar del PC de adquisición los originales, el identificador de sonda,
   sensibilidad, constante de resorte, fecha, frecuencia de muestreo, velocidad,
   filtro instrumental y controles. Vincular cada calibración con su sesión y
   conservar hashes y registros de Data Hunter, Validation y Phantoms cuando
   correspondan al mismo archivo.
2. Inventariar todas las curvas por muestra, sesión, ciclo y rama, incluidas
   las revisadas sin candidatos. Conservar la señal cruda. Superponer cada
   anotación y las dos rectas sobre los datos en orden de adquisición. Revisar
   saturación, cuantización, inversiones y transitorios de realimentación.
3. Fijar el rango de ventanas, las exclusiones y el protocolo de anotación antes
   de evaluar las curvas reservadas. Dos revisores pueden anotar de forma
   independiente. Medir sensibilidad a desplazar la frontera y a variar la
   ventana. Inyectar escalones de signo y duración conocidos en trazas de
   control, incluidas transiciones redondeadas por el ancho de banda.
4. Antes de automatizar la búsqueda, medir falsos eventos por curva de control,
   recuperación por amplitud y duración, error de localización y sesgo de
   amplitud en datos reservados por sesión o muestra. Acordar con el laboratorio
   los límites útiles en nN y en muestras antes de abrir ese conjunto.
5. Para una publicación, informar los denominadores por muestra independiente,
   la incertidumbre de calibración y la variabilidad entre muestras. Archivar
   originales permitidos, controles, anotaciones, exclusiones, receta y salidas.
   Citar el commit usado y el DOI de la versión archivada correspondiente.
   El DOI de una versión anterior describe esa versión.

### Contrastes con datos públicos y efecto de la frontera

`force-steps` exporta en `boundary_sensitivity` dos ajustes adicionales al mover
la frontera una muestra en cada dirección. Un vecino inviable conserva su
motivo de rechazo. La altura se identifica por el canal y los slots de
conversión o la unidad de entrada que expone el lector. En el phantom de +2 nN,
con ocho muestras por lado, mover la frontera una muestra dio un sesgo de
aproximadamente −0,91 nN. El lote conserva la medición central para poder
inspeccionar esa dependencia.

En la comparación pública de PAAm, el módulo de Hertz del gel rígido dependió
fuertemente de usar el canal de altura del piezo o una posición de punta
construida desde el sensor. Para interpretar módulos absolutos hace falta
verificar el eje y el protocolo de ajuste del instrumento. [Datos, métodos y resultados](validation/force-steps-public/README.md).
[Plan de validación, rendimiento e interfaz](design/force-validation-performance-fathom.md).

### Inspección interactiva en Fathom

Sobre el gráfico de fuerza, **Desplazar** mueve la vista y la rueda amplía alrededor del puntero. En **Zoom rectangular**, arrastrar un rectángulo amplía esos límites. **Reencuadrar** vuelve a mostrar la curva completa. La casilla **Ventana de ajuste** delimita por separado las muestras que se usan al ajustar el modelo.

En **Inspeccionar**, acercar el puntero a una traza muestra su nombre, índice (desde cero) y coordenadas. Puedes elegir una rama cuando las dos se superponen, o seleccionar el ajuste para leer sus puntos calculados. Un clic fija una referencia y el puntero muestra ΔX y ΔY con respecto a ella. La lectura corresponde a puntos de la traza que se visualiza en el eje seleccionado.

En **Ejes**, introduce mínimos y máximos, ajusta Y a las muestras del intervalo X visible o cambia las unidades de presentación. Las fuerzas se pueden leer en pN, nN o µN y las distancias en nm o µm. Para una señal de tensión se ofrecen mV y V. Cambiar unidades conserva el encuadre físico y los parámetros de la receta.

En **Apariencia**, elige la paleta de trazas y, si quieres, un fondo personalizado para los gráficos interactivos de líneas. Las escalas de color de las imágenes y mapas tienen sus propios controles.

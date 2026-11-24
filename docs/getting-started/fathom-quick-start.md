# Fathom quick start

Para procesar mapas NanoSurf, consulte la [guía P0 de NID y batch (PDF)](guia-p0-nid.pdf) o la [guía de medición de escalones](escalones-nid-fathom.md).

**SPM-Kit computes. Fathom lets the researcher inspect, configure and operate
those computations interactively.** Fathom is installed with SPM-Kit; it is not
a separate numerical package.

## First session

1. Install the GUI extra: `python -m pip install "spmkit[gui] @ git+https://github.com/kegouro/spmkit@main"`.
2. Launch `spmkit gui`, optionally followed by a file path.
3. Open a file with **Ctrl+O** or drag it onto the workspace.
4. Inspect the proposed routing. A mixed file may ask whether to open it as an image or force map.
5. Choose a perspective from the top bar or press **Ctrl+K** and search by name.
6. Configure the visible parameters. Record tip radius, fit model, leveling or thresholds when they affect the result.
7. Run the analysis and inspect the result, residuals, R² or other available quality indicators.
8. Export a figure/result/report as appropriate.
9. Save a `.spmproj` project with **Ctrl+S** when the workflow supports it.
10. Keep the source file, software version and exported provenance with the result.

## Which perspective?

| Intent | Display name in current code | Key |
|---|---|---|
| Topography, roughness and KPFM | Imagen | `image` |
| Particle segmentation | Granos | `grains` |
| PSD and self-affine analysis | Espectral | `spectral` |
| Cantilever spectrum | Sintonía térmica | `resonance` |
| Time-dependent resonance | Evaporación | `evaporation` |
| One force curve and contact fit | Curva de fuerza | `force` |
| Molecule-pulling events | SMFS | `smfs` |
| Force-volume properties | Mapa | `map` |
| Multiple files | Batch | `batch` |
| Publication output | Figura | `figure` |
| Surface rendering | Vista 3D | `view3d` |
| Educational cantilever simulation | Simulador | `simulator` |

Screenshots in this documentation are generated from deterministic synthetic
data by `scripts/gen_docs_media.py`; they are interface demonstrations, not
experimental validation.

[Open the complete Fathom tour](../ecosystem/fathom.md) ·
[Read the full manual](../user-guide.md)

## Force-map windows

In **Batch → Ventanas automáticas…**, select **Escalones de fuerza** or
**Contacto · Hertz esférico**, set the parameters, then choose the NID maps.
Select a result row to inspect the force trace against the acquisition index.
The shaded interval is inclusive. The vertical line marks the proposed step
boundary or the first post-contact sample. CSV exports include rows without a
measurement, sample indices starting at zero, source hashes, SI units in the
column names, parameters and the code revision when available.

- **Steps.** Select approach or retract, samples per side and noise multiplier.
  The selector screens consecutive force differences after removing a local
  slope. It measures isolated candidates by extrapolating two local lines to
  the same sensor height. It rejects close transitions and requires agreement
  with a shorter window. Slow transitions and unresolved neighbours can be
  missed. A candidate is a signal discontinuity, whose physical origin needs
  experimental controls.
- **Contact.** Enter the measured spherical tip radius, Poisson ratio and maximum
  fit depth. The mode uses the first 10% of approach as the pre-contact baseline,
  locates persistent repulsion, and refines the contact origin by a bounded Hertz
  fit. The final modulus uses only post-contact samples inside the specified
  depth. It requires a monotonic indentation coordinate, at least 12 fit samples,
  R² of 0.98 or greater, and agreement of the two half-window moduli within 25%
  of the full estimate. Check these assumptions for the material, probe and
  acquisition. Automatic selection and a good fit alone cannot establish
  that a liquid marble obeys spherical elastic contact mechanics. For the effect
  of contact location and fit depth on modulus estimates, see [Gavara (2016)](https://doi.org/10.1038/srep21267).

Use **Curva de fuerza → Ejes → Estilo de la curva…** for line widths and patterns,
axis stroke width, text size and axis titles. Display units follow the selected
physical quantity. **Ejes → Guardar vista del gráfico…** exports the visible
zoom, styles and residuals as vector SVG or PNG. Stroke and font preferences
persist locally. Axis aliases apply to the current acquisition.

## Revisar la adhesión de todas las curvas de un NID

1. En **Curva de fuerza**, abre el NID como **Mapa de curvas** y pulsa **Adhesión del mapa…**. Para comparar archivos, abre **Batch → Adhesión por curva… → Elegir mapas NID…** y selecciona varios. Cada fila representa una curva adquirida.
2. Selecciona un archivo y pulsa una fila o una celda del mapa. Verás las muestras completas de aproximación y retracción. El punto rojo identifica el mínimo de retracción y la línea horizontal, su referencia. Si falta separación en una rama, cambia a **Altura del sensor** para representar ambas sobre el mismo eje. Los índices empiezan en cero. La cuadrícula refleja el orden de adquisición según la forma inferida por el lector. Identificar una posición física en la imagen requiere conocer la geometría y el orden de barrido.
3. Todas las casillas empiezan marcadas. **Revisar siguiente aviso…** muestra el motivo y pide confirmación antes de excluir la curva. También puedes desmarcar o volver a marcar **Incluir**. La mediana usa las curvas seleccionadas que tienen medición. Las decisiones pertenecen a esta revisión; el batch convencional tiene su propia receta.
4. **Exportar curvas…** conserva cada medición, su índice, la recomendación y tu decisión. **Exportar resumen…** guarda los conteos y la mediana por archivo. **Exportar trazas completas…** escribe una fila por muestra de las ramas seleccionadas, con altura y separación en metros y fuerza en newtons. Las celdas de separación quedan vacías cuando ese canal no está disponible. Exporta las decisiones antes de cerrar Fathom.

La magnitud de adhesión se calcula sobre toda la retracción calibrada, en el orden de adquisición. La referencia es la mediana del último 10 % de muestras (mínimo cinco); el resultado es la diferencia positiva entre la referencia y el mínimo de fuerza. Verifica que la cola represente la punta ya despegada y que una fuerza atractiva tenga signo negativo. El visor señala mínimos en los bordes o en la cola, mínimos aislados y amplitudes pequeñas respecto al ruido de cola. Una adhesión baja puede ser real. Documenta cualquier criterio de exclusión aplicado al comparar muestras. La definición de fuerza de adhesión respecto a la línea base también se describe en [Nanoscale, figura 7](https://doi.org/10.1039/D3NR01568H).

### Exportar una figura por curva

En **Batch → Ventanas automáticas…**, analiza los archivos y pulsa **Exportar figuras por curva…**. Elige la carpeta de destino. Fathom crea una subcarpeta nueva con PNG a 300 ppp organizados por mapa. Cada imagen muestra las ramas disponibles a escala propia, la ventana usada y una ampliación local. Si hay varios candidatos en una curva, comparten una imagen. Si no hay candidato, se conserva la vista completa con el motivo. Los índices de curva y de muestra empiezan en cero.

En **Adhesión por curva… → Figuras…** puedes exportar directamente **Adhesión de las curvas incluidas…** (mínimo de retracción y referencia de cola), o elegir **Ventanas automáticas de las curvas incluidas…** para medir escalones o contacto con la selección actual. En este último caso pulsa **Analizar curvas incluidas** y después **Exportar figuras por curva…**.

La leyenda ocupa una esquina del encabezado. Cada eje lleva su unidad. Cuando las ramas carecen de una separación común utilizable, se representa la altura del sensor. La ampliación sigue las muestras adquiridas en el intervalo de análisis. La escala puede variar entre imágenes: compara amplitudes utilizando los valores numéricos y las unidades. `indice.csv` vincula las imágenes con el archivo original, su SHA-256 y la curva. Junto a él se guardan las ventanas calculadas o las decisiones de inclusión, según el modo.

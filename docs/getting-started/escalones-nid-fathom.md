# Medir escalones en curvas de fuerza NID con Fathom

Guía para el workspace de SPM-Kit con la corrección de longitudes NID de la revisión `2a425fc`. La interfaz permite localizar y anotar candidatos por muestra. La medición que corrige la pendiente local se ejecuta con `spmkit force-steps`. Ambas operaciones se hacen en el PC del laboratorio.

## 1. Preparar la sesión

- Conserva los NID originales y trabaja en una carpeta local autorizada. Guarda proyecto, figuras, tablas y notas en una carpeta de resultados. Los archivos exportados pueden incluir el nombre o la ruta local de la fuente.
- Pide al laboratorio la correspondencia archivo–muestra–control, el cantiléver, su constante de resorte en N/m, la sensibilidad inversa de la palanca óptica (InVOLS) en nm/V y sus incertidumbres, si se conocen. Anota la fecha de calibración, velocidad de rampa, frecuencia de muestreo, filtros de adquisición y cualquier cambio entre archivos.
- Acuerda qué ramas, curvas y región física revisarás. Lleva un listado de todas las curvas revisadas, también las que no tienen candidatos y las excluidas con su motivo.
- Para ensayar, el repositorio incluye `tests/validation/fixtures/force_foundation/spectroscopy.nid`. Sirve para aprender los controles y verificar la lectura. Los índices de ejemplo que aparecen abajo son ilustrativos.

## 2. Abrir la adquisición y comprobar los ejes

1. Abre Fathom con la instalación que contiene la corrección. El comando `spmkit workspace` abre directamente la interfaz descrita aquí.
2. Pulsa **Abrir…** o arrastra el NID a la ventana. Si aparece **Abrir como…**, elige **Mapa de curvas**. Se abre **Curva de fuerza**. Comprueba que el nombre del archivo y el total de curvas coinciden con el experimento.
3. En **Pipeline → Calibración**, deja **InVOLS** y **k resorte** en **0** para usar los metadatos del archivo. En el perfil NID de fuerza admitido, el canal de fuerza ya viene escalado. Contrasta la calibración con el registro del laboratorio. Evita estimar InVOLS con **Calcular** sobre la propia liquid marble. Si el lector rechaza la unidad o la escala, guarda el mensaje y acláralo con quien adquirió el archivo antes de cuantificar.
4. En **Pipeline → Ajuste**, usa **Suavizado = 0 pts** para la primera revisión. En el gráfico elige **Separación** y deja desmarcada **Ventana de ajuste**. Lee el título efectivo del eje X. **Altura** corresponde al sensor Z, **Separación** corresponde al eje de separación seleccionado por el programa y **Altura / Separación** indica que las ramas usan ejes distintos. Para cuantificar un escalón de fuerza, el eje Y debe indicar **Fuerza**. Una amplitud en voltios o una deflexión en nm requeriría otra conversión.
5. Usa el deslizador **Curva del volumen** para recorrer la adquisición. El contador empieza en 1. Para el archivo de anotaciones, la curva visible **2 / 100** tiene índice **1**.

## 3. Marcar un escalón con el ratón

1. Pulsa **Reencuadrar** para ver la rama completa. Busca un cambio localizado con muestras a ambos lados. Anota si coincide con el contacto inicial, la inversión de la rampa, el extremo de la curva o saturación. Si esos casos afectan a la interpretación, clasifícalos por separado.
2. En **Zoom rectangular**, arrastra sobre el candidato incluyendo un tramo a cada lado. **Ejes → Ajustar Y al intervalo X visible** amplía el detalle vertical. **Ejes → Límites manuales…** permite usar las mismas escalas en muestra y control. El zoom solo cambia la vista.
3. Cambia a **Inspeccionar** y selecciona explícitamente **Aproximación** o **Retracción**. Acerca el puntero a la traza. El texto muestra la rama, el índice entre corchetes y X e Y. Los índices siguen el orden de adquisición aunque X disminuya.
4. Haz clic en una muestra inmediatamente anterior al salto y mueve el puntero, sin hacer otro clic, a una posterior. Lee **ΔY** y **ΔX**. Un segundo clic cambia el punto de referencia. Usa **Borrar referencia** al terminar. Una pendiente de fondo también contribuye a ese ΔY.
5. Anota como frontera la **primera muestra después del salto**. Si ocurre entre [119] y [120], la frontera es 120. Si el cambio se extiende por varios puntos y la frontera es ambigua, anótalo en tus notas. Conserva el signo del salto.
6. Para cada candidato registra archivo, curva, rama, índice, ventana de análisis, unidades y observaciones. Registra por separado la revisión de controles y curvas sin candidato. La referencia del ratón es temporal. El proyecto, el JSON del ajuste y la exportación del lote no crean esta tabla.

## 4. Repetir la medición a partir de tus anotaciones

En un editor de texto o una hoja de cálculo crea `anotaciones.csv`, en UTF-8, con coma como delimitador y exactamente estas seis columnas. La ruta de `source` es relativa a la carpeta del CSV. Si la carpeta del proyecto contiene las subcarpetas `originales` y `resultados`, y guardas el CSV en `resultados`, puedes usar este ejemplo.

```csv
source,curve,branch,cycle,boundary,window
../originales/M01.nid,1,extend,0,120,8
```

La fila representa la segunda curva visible, en aproximación (`extend`). Para retracción usa `retract`. Usa ciclo `0` para el primer segmento de esa rama. `window=8` usa ocho muestras antes y ocho después. Es un ejemplo. Fija la ventana con los controles y el muestreo, con tramos aproximadamente lineales y sin incluir otro escalón. Documenta los cambios de ventana y compara su efecto. La operación requiere tres muestras como mínimo a cada lado y altura estrictamente monótona en el tramo.

Desde una terminal abierta en la carpeta del CSV, con la misma instalación de SPM-Kit, ejecuta lo siguiente. Usa un nombre de salida nuevo para cada revisión.

```sh
spmkit force-steps anotaciones.csv > escalones_r01.jsonl
```

Cada línea corresponde a una anotación. `status="measured"` indica que se pudo calcular. `delta_force_n` es la diferencia entre dos rectas locales evaluadas a la misma altura del sensor, con signo posterior menos anterior. Multiplica por 1 000 000 000 para expresarla en nN. `height_m` es la posición en el sensor Z. `boundary_sensitivity` repite el cálculo moviendo la frontera una muestra en cada dirección. `left_residual_rms_n` y `right_residual_rms_n` describen la dispersión alrededor de cada recta. Conserva los casos con `status="rejected"` y revisa `reason`. Estos diagnósticos por sí solos no establecen la incertidumbre experimental ni el origen físico del evento.

## 5. Guardar y contrastar

- **Guardar proyecto…** conserva referencias y ajustes. Mantén los originales accesibles en su ubicación. **Exportar curva…** guarda el CSV de la curva procesada cuando hay un resultado disponible. En la paleta de comandos puedes buscar **Exportar resultados (JSON)…** para conservar índice, receta y hash del original cuando haya resultados del ajuste. El JSONL de escalones es el generado en el paso 4.
- En el mismo PC, contrasta varias ramas con una exportación numérica de Nanosurf o con otro lector como NSFopen. Compara la misma curva, rama, canal y muestras en las mismas unidades. Comprueba el número de puntos adquiridos, el signo y los valores de fuerza y altura alrededor de las fronteras. Si el segundo programa muestra separación y el primero altura Z, selecciona el mismo canal físico antes de comparar.
- Aplica el mismo criterio a un control comparable, adquirido idealmente con el mismo cantiléver y ajustes. Comprueba si aparecen saltos similares, si los candidatos se repiten en adquisiciones independientes y cuánto varía la amplitud al cambiar ligeramente la frontera o la ventana. Distingue número de muestras físicas, adquisiciones, curvas revisadas y eventos.
- Conserva juntos la revisión de SPM-Kit, la calibración, los originales, el proyecto, las anotaciones, el JSONL, el registro de controles y las figuras. Si solo tienes la interfaz, puedes terminar la inspección y guardar las anotaciones. La cuantificación con rectas locales se puede reproducir más tarde con el mismo CSV.

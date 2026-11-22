# Contraste público de escalones de fuerza y módulos AFM

**22 de noviembre de 2026.** Se comprobaron la lectura con unidades, la medición de amplitud en una frontera anotada, su ejecución en lote y el ajuste Hertz de curvas reales. La evidencia experimental procede de dos depósitos públicos. Los datos del experimento de liquid marbles y sus calibraciones siguen en el laboratorio.

## Búsqueda y selección

SPM-Kit Data Hunter consultó DataCite con cuatro expresiones. La campaña devolvió siete identificadores, correspondientes a tres conjuntos al agrupar sus versiones. La búsqueda específica de liquid marbles dio cero registros con esa expresión. La clasificación automática de Hunter fue Bronze en los siete registros. Seleccionamos los dos primeros conjuntos para ensayos con originales descargables. [SPM-Kit Data Hunter, revisión utilizada](https://github.com/kegouro/spmkit-data-hunter/tree/852af89e27585dc2239148a272f41200cbe4b658)

| Depósito | Alcance en este contraste |
| --- | --- |
| FranzeLab, Rheinlaender y Franze, *Force curves raw data*, v1, CC BY 4.0 | Pares JPK/TXT de una misma adquisición. Se compararon señales y amplitudes en dos representaciones. [Figshare](https://doi.org/10.6084/m9.figshare.10732415.v1) |
| Rosso, Müller y Guck, *Atomic force microscopy indentation data of stiff and compliant polyacrylamide hydrogels*, v3, CC0 | Las 110 curvas publicadas con los SHA-256 de los autores. Se contrastaron el lote y dos programas de ajuste. El inventario histórico de diez curvas del repositorio es un subconjunto. [Figshare](https://doi.org/10.6084/m9.figshare.11637675.v3) |
| *Colloidal probe atomic force microscopy measurements on pristine gas bubbles, agglomerates and particle-laden gas bubbles* | Candidato para ensayar controles de interfaz. Los autores describen corrección de línea base. En esta campaña se revisó el registro bibliográfico. [OPARA](https://doi.org/10.25532/OPARA-536) |

## Lectura JPK, cálculo individual y lote

Se tomaron el primer y último par por ruta en orden lexicográfico de cada grupo del ZIP, con 239 pares elegibles en beads, 268 en beads with brush, 1150 en fibroblasts y 1075 en microglia. La selección incluye curvas de sustrato. Se verificaron los hashes de ocho binarios y ocho textos. En 18 segmentos, incluidas dos pausas, se compararon **50 000 muestras** en orden de adquisición. El TXT expresa la altura en el slot nominal. Cada bloque se convirtió con su `heightMultiplier` y `heightOffset` para compararlo con la altura calibrada del lector. Comparar ambas columnas sin esa conversión llegó a producir una diferencia aparente de 26,84 µm.

| Comparación | Máxima diferencia absoluta |
| --- | ---: |
| Fuerza JPK frente a TXT | 1,63 × 10⁻¹⁵ N |
| Altura calibrada JPK frente a TXT convertido | 5,08 × 10⁻¹² m (cota redondeada hacia arriba) |
| ΔF de SPM-Kit frente a dos regresiones independientes sobre el TXT | 2,28 × 10⁻¹⁵ N |

Se fijó una frontera de diagnóstico en la muestra central de cada rama de aproximación y retracción, con ocho muestras a cada lado. La referencia evalúa dos rectas en la misma altura central mediante una matriz de diseño y `numpy.linalg.lstsq`. Las 16 amplitudes del lote coincidieron exactamente con el cálculo individual. Estas posiciones se escogieron antes de inspeccionar la señal. El contraste verifica la implementación en archivos reales. La identidad física de un posible evento requiere anotaciones y controles experimentales. [Manifiesto](pairs.json) · [Resultados por segmento](paired-batch-crosscheck.jsonl)

## Sensibilidad a anotar un escalón una muestra antes o después

SPM-Kit Phantoms generó una superficie escalonada de 256 filas × 80 columnas por nivel. Se interpretó cada fila como una deflexión impuesta, se multiplicó por una constante de 0,2 N/m y se superpuso una rampa de fuerza de 0,4 N/m. El muestreo en altura fue de 1 nm y el ruido blanco gaussiano tuvo desviación de 0,1 nN. Se ensayaron saltos de −2, 0 y +2 nN, tres ventanas y tres fronteras. Se reutilizó la misma realización de ruido entre condiciones para comparaciones pareadas. Las 256 filas de cada condición son realizaciones sintéticas. [SPM-Kit Phantoms, revisión utilizada](https://github.com/kegouro/spmkit-phantoms/tree/ab994cea1da484247a36c304be03da746fa059df)

| Frontera, salto +2 nN y ocho muestras por lado | Sesgo (nN) | RMSE (nN) |
| --- | ---: | ---: |
| Una muestra antes | −0,9060 | 0,9120 |
| Muestra especificada por el generador | +0,0013 | 0,0956 |
| Una muestra después | −0,9153 | 0,9213 |

El JSONL de `force-steps` permite revisar por anotación las dos estimaciones vecinas. El intervalo entre estas cifras describe sensibilidad local. Para expresar incertidumbre experimental hacen falta la calibración, el ancho de banda, la estructura del ruido y el procedimiento de selección de candidatos. [Resultados de las 27 configuraciones](phantom-windows.csv)

## Hidrogeles PAAm y efecto del eje usado para Hertz

El depósito describe dos geles y seis regiones de interés por gel, con 55 curvas por gel. Los autores indican sonda esférica de radio 5 µm, constante de 0,08 N/m y calibración térmica en PBS. Los intervalos de módulo describen valores esperados del protocolo de preparación. Se fijó ν = 0,3 para esta comparación y se analizó la aproximación. Todas las cifras de la tabla son medianas por curva en kPa. Las curvas de un gel son mediciones repetidas.

| Material | Esperado según autores | SPM-Kit, lote habitual | SPM-Kit, cambiando solo el eje | SPM-Kit, entradas de nanite | nanite 4.2.3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compliant | 0,8–1,2 | 1,5763 | 1,2746 | 1,2746 | 1,2929 |
| Stiff | 25–28 | 4,9567 | 33,1964 | 33,1964 | 33,2682 |

1. El lote `fbatch` utilizó el radio publicado de 5 µm y produjo un módulo finito en 110 de 110 archivos. Los 110 valores exportados coincidieron exactamente con el ajuste individual de SPM-Kit sobre su eje habitual en esta ejecución. Para estos JPK el lector construye la separación a partir de `height` calibrado menos la deflexión.
2. Con el mismo vector de fuerza nativo y el mismo ajuste SPM-Kit se sustituyó únicamente el eje por la altura medida obtenida mediante afmformats más F/k antes de corregir offsets. Ese cambio por sí solo reprodujo el desplazamiento principal de los módulos.
3. Se repitió SPM-Kit con las mismas posiciones y fuerzas de aproximación ya preprocesadas por nanite. Se comparó con el modelo `hertz_para` de nanite, radio y ν fijos, segmento 0, peso de proximidad al contacto desactivado. En las 110 comparaciones sobre entradas iguales, la mayor diferencia relativa individual respecto a nanite fue del 0,37 % en el gel rígido y del 1,87 % en el blando. [Documentación de ajuste de nanite](https://nanite.readthedocs.io/en/stable/sec_fitting_guide.html)
4. La cercanía entre programas con entradas iguales localiza una dependencia del eje en este conjunto. Ambos quedan por encima de los intervalos esperados con esa receta. Para validar exactitud absoluta hay que contrastar la posición de punta frente a una exportación del instrumento, el rango de indentación, la elección del contacto y los parámetros del protocolo. Los resultados se publican por curva y con nombres que identifican la ROI. [Tabla pareada y hashes](paam-axis-crosscheck.csv)

## Reproducción

Desde la raíz del repositorio, usar Python 3.12 y un directorio de salida nuevo. Para repetir la búsqueda desde una instalación de la revisión indicada de Data Hunter:

```sh
spmkit-data-hunter campaign create force-interfaces --source datacite \
  --query '"Colloidal probe atomic force microscopy measurements"' \
  --query '"Atomic force microscopy indentation data of stiff and compliant polyacrylamide hydrogels"' \
  --query '"liquid marbles" AND "force spectroscopy"' --query '"Force curves raw data"' \
  --max-runtime 90 --max-records 40 --page-size 10 --output hunter
spmkit-data-hunter campaign run force-interfaces --output hunter
```

Para el estudio JPK/TXT y los phantoms se utilizó NumPy 2.5.1. La descarga por rangos recupera solo los miembros del ZIP enumerados en el manifiesto. La descarga PAAm verifica cada fichero contra el SHA-256 de los autores.

```sh
study=docs/validation/force-steps-public
python3.12 -m venv .venv-force-study
. .venv-force-study/bin/activate
python -m pip install -c requirements-reproducible.txt -e '.[jpk]' remotezip==0.12.6 \
  'spmkit-phantoms @ git+https://github.com/kegouro/spmkit-phantoms.git@ab994cea1da484247a36c304be03da746fa059df'
python "$study/fetch_inputs.py" pairs inputs/pairs
python "$study/compare_jpk_text.py" inputs/pairs > pairs-result.jsonl
python "$study/phantom_windows.py" > windows-result.csv
python "$study/fetch_inputs.py" paam inputs/paam
spmkit fbatch inputs/paam --tip-radius 5e-6 -o paam-fbatch.csv
deactivate
```

El contraste independiente se ejecutó en un segundo entorno con Python 3.12.13, nanite 4.2.3, afmformats 0.18.7, lmfit 1.3.4, NumPy 2.5.5 y SciPy 1.18.1. El script emite los módulos en Pa y comprueba los hashes y el número de curvas. Para cotejar la salida con `fbatch`, unir por nombre de archivo y SHA-256.

```sh
python3.12 -m venv .venv-force-compare
. .venv-force-compare/bin/activate
python -m pip install -e '.[jpk]' nanite==4.2.3 afmformats==0.18.7 \
  lmfit==1.3.4 numpy==2.5.5 scipy==1.18.1
python "$study/compare_paam.py" inputs/paam inputs/paam/sha256.txt paam-fbatch.csv > paam-result.csv
```

Para citar este estudio, identificar la revisión Git de SPM-Kit, las revisiones de los programas auxiliares y los DOI versionados de ambos depósitos. La tabla de módulos corresponde a la receta y a los entornos especificados. [Plan para validación experimental, escalado y Fathom](../../design/force-validation-performance-fathom.md)

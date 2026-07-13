# Validación científica del manejo de datos

Este documento resume cómo se verificó que spmkit lee e interpreta los datos
del instrumento de forma correcta, para dar confianza científica a los
resultados. Las pruebas viven en `tests/validation/` y se ejecutan con
`pytest tests/validation` (se omiten si no están los archivos del lab).

## Alcance por formato

| Formato | Evidencia disponible | Estado |
|---------|----------------------|--------|
| `.nid` | Comparación externa contra exportaciones de Gwyddion | Validado externamente |
| `.gwy` | Escritura y relectura con igualdad de datos | Round-trip reproducible |
| `.nhf` | Archivos HDF5 sintéticos que ejercitan el contrato público | Experimental |

El lector `.nhf` conserva datos y atributos del esquema genérico que recibe,
ignora datasets que no son 2D y reporta archivos ilegibles. Estas pruebas no
constituyen validación contra un instrumento ni contra un oráculo externo.

## 1. Validación contra ground truth (Gwyddion)

Se comparó la lectura del `.nid` (crudo del instrumento) contra el `.gwy`
exportado por el Gwyddion del lab **para una misma medida** (un barrido de
topografía con canales de imagen y espectroscopía).

| Canal | Resultado |
|-------|-----------|
| Phase (fwd/bwd) | **corr = 1.000000**, error de relieve `0.0` |
| Z-Axis Sensor (fwd/bwd) | **corr = 1.000000**, error de relieve `0.0` |
| Z-Axis backward | **corr = 1.000000**, error de relieve `0.0` |
| Z-Axis forward | corr 1.0 **tras nivelar** (el lab lo niveló en Gwyddion) |

**Conclusiones:**

1. La conversión a unidades físicas
   `phys = Dim2Min + (raw + 2^(b-1)) / 2^b · Dim2Range`
   es **exacta a precisión de máquina** en todos los canales.
2. La diferencia en *Z-Axis forward* resultó ser **exactamente un plano**
   (residuo ≈ 10⁻²¹ tras ajuste de plano): es la nivelación que el lab aplicó
   en Gwyddion, no un error de lectura.

## 2. Orientación de imagen

Gwyddion almacena las imágenes con un volteo vertical respecto al orden de
líneas crudo de NanoSurf. spmkit aplica `flipud` **solo a los canales de
imagen** (`Dim1Name = Y*`) para que lo que se ve en spmkit coincida
exactamente con Gwyddion/NanoSurf.

Los canales de **espectroscopía** (`Dim1Name = SpecPoint`, curvas
fuerza-distancia) **no se voltean**: sus filas son curvas independientes y
voltearlas reasignaría mal la posición espacial de cada medida. Esto se
verifica en `test_nanomech_real.py` (el módulo de Young estimado es estable y
repetible entre curvas de la misma medida).

## 3. Robustez

- Los **21 archivos `.nid`** del lab cargan sin error, con datos finitos,
  incluyendo barridos cuadrados (256², 512²) y espectroscopía no cuadrada
  (100×1024).
- Lectura de archivos **truncados/corruptos** falla con un error claro en vez
  de devolver datos basura (guardia de tamaño en el parser).
- Round-trip `.gwy` (escribir y releer) es exacto.

## 4. Rugosidad y nanomecánica

- Rugosidad (ISO 25178): verificada con superficies sintéticas de σ conocido
  (`Sq` recupera σ) y con superficie plana (todos los parámetros → 0).
- Nanomecánica: el ajuste de Hertz recupera el módulo de Young de una curva
  sintética con error < 5 % y detecta el punto de contacto.

## Cómo reproducir

```bash
pip install -e ".[dev,gwy]"
pytest tests/validation -v
```

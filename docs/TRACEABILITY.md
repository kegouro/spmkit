# Verificación y Trazabilidad del Pipeline `.nid`

Este documento describe el pipeline de datos completo para archivos NanoSurf `.nid`
y las verificaciones de integridad que garantizan que cada etapa se ejecuta correctamente.

## Visión general

```
Archivo .nid (bytes)
    │
    ▼
[1] Extracción del header
    ├── Localización del marcador #! (offset exacto)
    ├── Decodificación UTF-8 / latin-1
    └── Parseo INI → secciones/claves
    │
    ▼
[2] Construcción del orden de canales
    └── _channel_order(DataSet) → lista de secciones DataSet-G:C
    │
    ▼
[3] Lectura de bloques binarios (por canal)
    ├── offset acumulado (bin_start + suma anterior)
    ├── dtype inferido de SaveBits/SaveSign/SaveOrder
    ├── np.frombuffer → array int32 LE (Lines × Points)
    └── verificación de que no excede EOF
    │
    ▼
[4] Conversión a unidades físicas
    ├── signed: phys = Dim2Min + (raw + 2^(bits-1)) / 2^bits * Dim2Range
    └── unsigned: phys = Dim2Min + raw / (2^bits - 1) * Dim2Range
    │
    ▼
[5] Orientación
    ├── Dim1Name empieza con "Y" → imagen → np.flipud (como Gwyddion)
    └── otros (SpecPoint, …) → sin voltear
    │
    ▼
[6] Modelo de dominio (SPMChannel / SPMData)
    │
    ├── [A] Análisis: roughness, KPFM, espectral, nanomecánica…
    ├── [B] Exportación: CSV, JSON, HDF5, GWY
    └── [C] Visualización: figure, report
```

## Módulo `spmkit.core.verify`

El módulo `verify.py` implementa la función `trace_nid` que recorre este pipeline
y registra métricas de trazabilidad en un objeto `NidTrace`.

### `trace_nid(path) -> NidTrace`

Abre el archivo byte a byte y realiza las siguientes operaciones:

| Etapa | Información capturada |
|---|---|
| Localización del marcador | `marker_offset`, `binary_bytes` |
| Decodificación del header | éxito/fallo, longitud en caracteres |
| Parseo INI | `n_sections` |
| Orden de canales | `n_channels` |
| Por canal | `byte_offset`, `byte_length`, `dtype`, `points`, `lines`, `raw_min`, `raw_max`, `phys_min`, `phys_max`, `x_range_m`, `y_range_m`, `flipped` |

### Verificaciones de integridad

| # | Nombre del check | Qué comprueba |
|---|---|---|
| 1 | marcador #! presente | El byte sequence `#!` existe en el archivo |
| 2 | header decodifica (UTF-8/latin-1) | El header es texto válido |
| 3 | sección [DataSet] presente | El INI contiene la sección raíz |
| 4 | suma de bloques binarios == bytes tras el marcador | No faltan ni sobran bytes |
| 5 | ningún canal excede el tamaño del archivo | No hay truncación |
| 6 | todos los datos finitos (sin NaN/Inf) | No hay valores inválidos tras la conversión |
| 7 | phys dentro de [Dim2Min, Dim2Min+Dim2Range] | El mapeo lineal está dentro del rango declarado |
| 8 | ejes X/Y > 0 para canales de imagen | Las dimensiones físicas son positivas |

### Ejemplo de uso en Python

```python
from spmkit.core.verify import trace_nid, format_report

trace = trace_nid("mi_archivo.nid")
print(format_report(trace))

if not trace.ok:
    failed = [c.name for c in trace.checks if not c.passed]
    raise RuntimeError(f"Checks fallidos: {failed}")
```

### Ejemplo de uso en CLI

```bash
spmkit verify mi_archivo.nid
```

La salida muestra:

1. Una tabla con todos los canales (offset, bytes, forma, rango raw y físico, si está volteado).
2. Una tabla de verificaciones con iconos `✓` (verde) / `✗` (rojo).
3. Un mensaje final `VERIFICACIÓN OK` o `VERIFICACIÓN FALLIDA` (con salida 1).

## Mapeo raw → físico (detalles)

Para `SaveBits=32`, `SaveSign=Signed`, `SaveOrder=Intel` (el caso más común):

- Tipo numpy: `<i4` (int32 little-endian)
- Rango entero: `[−2 147 483 648, 2 147 483 647]`
- Normalización: `norm = (raw + 2^31) / 2^32`
  - `raw = −2^31` → `norm = 0` → `phys = Dim2Min`
  - `raw = 0` → `norm = 0.5` → `phys = Dim2Min + 0.5 × Dim2Range`
  - `raw = 2^30` → `norm = 0.75` → `phys = Dim2Min + 0.75 × Dim2Range`
  - `raw → +∞` → `norm → 1` → `phys → Dim2Min + Dim2Range`

## Orientación vertical

NanoSurf almacena las filas de **arriba hacia abajo** (primera línea escaneada primero),
pero Gwyddion y la convención estándar las muestran **de abajo hacia arriba**.
Por eso, `load_nid` aplica `np.flipud` a todos los canales cuyo `Dim1Name` empieza
por `"Y"` (ejes Y espaciales). Los canales de espectroscopía (`Dim1Name=SpecPoint`)
no se voltean porque sus filas son curvas independientes.

## Presupuesto de bytes

El check más crítico es:

```
suma(Points_i × Lines_i × SaveBits_i / 8) == len(blob) − marker_offset − 2
```

Si no se cumple, el archivo está truncado, tiene canales adicionales no declarados,
o hay padding inesperado.

## Suite de tests

Los tests de trazabilidad están en `tests/validation/test_traceability.py` y cubren:

- `TestExtraction` — verificación de offsets y longitudes exactas con un `.nid` sintético
- `TestFormat` — mapeo raw→físico con `pytest.approx` para valores conocidos
- `TestByteBudget` — presupuesto de bytes
- `TestOrientation` — flip de imagen vs. no flip de espectroscopía
- `TestManipulation` — `roughness.statistics` sobre datos de σ conocida
- `TestRepresentation` — round-trips CSV, JSON, HDF5, GWY
- `TestCalculation` — `trace.ok is True` sobre archivo sintético
- `test_real_nid_trace_ok` — archivos reales (skip si no están en `reference/`)

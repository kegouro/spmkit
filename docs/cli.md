# Referencia CLI

spmkit expone una CLI construida con [Typer](https://typer.tiangolo.com/) y [Rich](https://github.com/Textualize/rich).

Los comandos de imagen aceptan `.nid`, `.gwy` y `.nhf`; el lector `.nhf` es experimental.

```bash
spmkit --help
```

---

## Opciones globales

| Opción | Descripción |
|--------|-------------|
| `--version`, `-V` | Muestra la versión y sale |
| `--help` | Muestra ayuda |

---

## `spmkit info`

Muestra metadatos y canales del archivo.

```bash
spmkit info FILE
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `FILE` | Ruta al archivo `.nid`, `.gwy` o `.nhf` experimental |

**Ejemplo:**

```bash
spmkit info scan.nid
```

Salida (tabla Rich):

```
          scan.nid  ·  formato nid
┌────────┬───────────┬─────────────────────┬─────────┬────────┬────────────────┐
│ Canal  │ Dirección │ Grupo               │ Forma   │ Unidad │ Tamaño X·Y     │
├────────┼───────────┼─────────────────────┼─────────┼────────┼────────────────┤
│ Z-Axis │ forward   │ Topography forward  │ 256×256 │ m      │ 5.00×5.00 µm   │
│ Z-Axis │ backward  │ Topography backward │ 256×256 │ m      │ 5.00×5.00 µm   │
│ CPD    │ forward   │ Potential forward   │ 256×256 │ V      │ 5.00×5.00 µm   │
└────────┴───────────┴─────────────────────┴─────────┴────────┴────────────────┘
```

---

## `spmkit roughness`

Calcula estadísticas de rugosidad areal sobre el canal seleccionado.

```bash
spmkit roughness FILE [OPTIONS]
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `FILE` | Archivo `.nid`, `.gwy` o `.nhf` experimental |

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a analizar |
| `--direction` | — | Dirección del canal |
| `--group` | — | Grupo del canal |
| `--level`, `-l` | `plane` | Nivelación: `plane` \| `poly` \| `rows` \| `none` |

**Ejemplo:**

```bash
spmkit roughness scan.gwy -c Z-Axis --direction forward --level plane
```

La tabla usa los nombres reales del resultado: `Sa`, `Sq`, `Sz`, `Sp`, `Sv`, `Ssk`, `Sku`,
`unit` y `n_points`.

Si el nombre identifica más de un canal, añade `--direction`; si la selección continúa
ambigua, añade `--group`. Consulta ambos valores con `spmkit info FILE`.

---

## `spmkit profile`

Extrae un perfil entre dos coordenadas `(X, Y)` de píxel y lo guarda como CSV.

```bash
spmkit profile FILE --x1 X --y1 Y [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a analizar |
| `--direction` | — | Dirección del canal |
| `--group` | — | Grupo del canal |
| `--x0`, `--y0` | `0.0`, `0.0` | Punto inicial en píxeles |
| `--x1`, `--y1` | requeridos | Punto final en píxeles |
| `--n` | auto | Número de muestras |
| `--level`, `-l` | `plane` | `plane` \| `poly` \| `rows` \| `none` |
| `--output`, `-o` | `profile.csv` | CSV de salida |

```bash
spmkit profile scan.gwy --direction forward \
  --x0 0.5 --y0 0.5 --x1 5.5 --y1 3.5 --n 3 \
  --level none --output profile.csv
```

Los extremos deben quedar dentro de la imagen. El encabezado del archivo es
`distance[m],height[unidad]`, donde `unidad` es la unidad física del canal.

---

## `spmkit analyze`

Pipeline completo: rugosidad (+ KPFM si hay canal CPD) → CSV + JSON.

```bash
spmkit analyze FILE [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--output`, `-o` | `./results` | Carpeta de salida |
| `--channel`, `-c` | `Z-Axis` | Canal de topografía |
| `--direction` | — | Dirección del canal de topografía |
| `--group` | — | Grupo del canal de topografía |
| `--cpd-channel` | `CPD` | Canal KPFM |
| `--cpd-direction` | — | Dirección del canal CPD |
| `--cpd-group` | — | Grupo del canal CPD |
| `--level`, `-l` | `plane` | `plane` \| `poly` \| `rows` \| `none` |
| `--tip-wf` | — | Función de trabajo de la punta (eV) |

**Ejemplo:**

```bash
spmkit analyze scan.gwy --output ./out \
  --channel Z-Axis --direction forward \
  --cpd-channel CPD --cpd-direction forward --tip-wf 4.7
```

Genera:

- `out/scan_roughness.csv` y `out/scan_roughness.json`
- `out/scan_kpfm.csv` y `out/scan_kpfm.json` (si existe canal CPD)

---

## `spmkit nanomech`

Ajusta una curva fuerza-distancia (modelo de Hertz) y estima el módulo de Young.

```bash
spmkit nanomech FILE [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Deflection` | Canal de fuerza (N) |
| `--curve` | `-1` | Índice de curva (`-1` = la del centro) |
| `--tip-radius` | `10e-9` | Radio de punta (m) |
| `--model` | `sphere` | Modelo: `sphere` \| `paraboloid` \| `cone` |
| `--spring-constant` | — | Constante de resorte del cantiléver (N/m) |

**Ejemplo:**

```bash
spmkit nanomech spec.nid --tip-radius 10e-9 --model dmt --contact-method rov
```

Salida *(valores ilustrativos con datos de ejemplo)*:

```
     Nanomecánica · curva 50/100 · dmt
┌──────────────────────┬────────────────────┐
│ Parámetro            │              Valor │
├──────────────────────┼────────────────────┤
│ Módulo de Young      │   4.50 ± 0.08 MPa  │
│ R²                   │            0.99921 │
│ Punto de contacto    │           12.45 nm │
│ Adhesión             │            3.21 nN │
│ RMSE                 │          1.234e-11 │
│ Puntos ajustados     │                214 │
└──────────────────────┴────────────────────┘
```

`--model` acepta `sphere`, `paraboloid`, `cone` y `dmt` (Hertz con adhesión);
`--contact-method` acepta `threshold` (rápido) o `rov` (robusto al ruido).

---

## `spmkit grains`

Detecta granos o partículas y muestra estadísticas de tamaño.

```bash
spmkit grains FILE [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal de topografía |
| `--threshold`, `-t` | auto | Umbral de altura en unidades del canal |
| `--min-size` | `4` | Tamaño mínimo del grano en píxeles |
| `--relative-height` | `0.5` | Fracción para umbral automático (0..1] |

**Ejemplo:**

```bash
spmkit grains scan.nid --min-size 10
```

---

## `spmkit batch`

Procesa todos los archivos SPM de una carpeta y genera una tabla resumen CSV.

```bash
spmkit batch FOLDER [OPTIONS]
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `FOLDER` | Carpeta con `.nid`, `.gwy` o `.nhf` experimental |

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a procesar |
| `--output`, `-o` | `batch_summary.csv` | Archivo CSV de salida |

**Ejemplo:**

```bash
spmkit batch ./medidas/ --output summary.csv
```

---

## `spmkit figure`

Exporta una figura de publicación con barra de escala y colormap científico.

```bash
spmkit figure FILE [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a visualizar |
| `--direction` | — | Dirección del canal |
| `--group` | — | Grupo del canal |
| `--output`, `-o` | `figure.png` | Archivo de salida (`.png`, `.svg`, `.pdf`) |
| `--colormap` | `gold` | Colormap |
| `--title` | (nombre del canal) | Título de la figura |

**Ejemplo:**

```bash
spmkit figure scan.gwy -c Z-Axis --direction forward -o topografia.svg
```

---

## `spmkit convert`

Convierte entre formatos (`.nid` → `.gwy`, `.nid` → `.h5`, etc.).

```bash
spmkit convert INPUT OUTPUT
```

**Formatos de salida soportados:**

| Extensión | Formato |
|-----------|---------|
| `.gwy` | Gwyddion (abre en Gwyddion directamente) |
| `.h5`, `.hdf5` | HDF5 |

**Ejemplo:**

```bash
spmkit convert scan.nid scan.gwy
```

---

## `spmkit evaporation`

Sensado de masa por evaporación: sigue f(t) → masa y tasa de evaporación. Ajusta la ley d² (evaporación limitada por difusión).

```bash
spmkit evaporation FOLDER [OPTIONS]
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `FOLDER` | Carpeta con espectros de thermal tuning (archivos `.nid`) |

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--spring-constant`, `-k` | (del archivo) | Constante de resorte (N/m) |
| `--position`, `-x` | `1.0` | Posición de carga x/L |
| `--output`, `-o` | — | CSV de salida |

**Ejemplo:**

```bash
spmkit evaporation ./tuning_series/ -k 0.3 --output evap.csv
```

---

## `spmkit psd`

Análisis espectral: dimensión fractal, exponente de Hurst y longitud de correlación.

```bash
spmkit psd FILE [OPTIONS]
```

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a analizar |
| `--direction` | — | Dirección del canal |
| `--group` | — | Grupo del canal |

**Ejemplo:**

```bash
spmkit psd scan.gwy -c Z-Axis --direction forward
```

Salida:

```
   Espectral · Z-Axis · scan.nid
┌────────────────────────────┬───────────┐
│ Parámetro                  │     Valor │
├────────────────────────────┼───────────┤
│ Dimensión fractal D        │    2.3142 │
│ Exponente de Hurst H       │    0.6858 │
│ Pendiente β (PSD)          │   -2.3716 │
│ R² (ajuste log-log)        │    0.9921 │
│ Longitud de correlación    │  312.45 nm│
└────────────────────────────┴───────────┘
```

---

## `spmkit gui`

Lanza la interfaz gráfica (requiere el extra `gui`).

```bash
spmkit gui [FILE]
```

`FILE` es opcional; cuando se indica, Fathom intenta abrirlo al arrancar.

!!! tip
    Si ves `ImportError`, instala el extra: `pip install "spmkit[gui]"`

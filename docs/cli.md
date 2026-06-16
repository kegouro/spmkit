# Referencia CLI

spmkit expone una CLI construida con [Typer](https://typer.tiangolo.com/) y [Rich](https://github.com/Textualize/rich).

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
| `FILE` | Ruta al archivo `.nid` o `.nhf` |

**Ejemplo:**

```bash
spmkit info scan.nid
```

Salida (tabla Rich):

```
          scan.nid  ·  formato nid
┌──────────────────┬───────────┬───────────┬────────┬────────────────┐
│ Canal            │ Dirección │ Forma     │ Unidad │ Tamaño X·Y     │
├──────────────────┼───────────┼───────────┼────────┼────────────────┤
│ Z-Axis           │ forward   │ 256×256   │ m      │ 5.00×5.00 µm   │
│ Z-Axis           │ backward  │ 256×256   │ m      │ 5.00×5.00 µm   │
│ Phase            │ forward   │ 256×256   │ °      │ 5.00×5.00 µm   │
│ CPD              │ forward   │ 256×256   │ V      │ 5.00×5.00 µm   │
└──────────────────┴───────────┴───────────┴────────┴────────────────┘
```

---

## `spmkit roughness`

Calcula parámetros de rugosidad areal (ISO 25178).

```bash
spmkit roughness FILE [OPTIONS]
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `FILE` | Archivo `.nid` o `.nhf` |

**Opciones:**

| Opción | Por defecto | Descripción |
|--------|-------------|-------------|
| `--channel`, `-c` | `Z-Axis` | Canal a analizar |
| `--level`, `-l` | `plane` | Nivelación: `plane` \| `poly` \| `none` |

**Ejemplo:**

```bash
spmkit roughness scan.nid -c Z-Axis --level plane
```

Salida:

```
   Rugosidad · Z-Axis (m)
┌───────────┬──────────────┐
│ Parámetro │        Valor │
├───────────┼──────────────┤
│ sa        │    2.388e-08 │
│ sq        │    3.901e-08 │
│ sz        │    2.205e-07 │
│ ssk       │       2.4395 │
│ sku       │       8.2629 │
└───────────┴──────────────┘
```

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
| `--cpd-channel` | `CPD` | Canal KPFM |
| `--level`, `-l` | `plane` | Nivelación |
| `--tip-wf` | — | Función de trabajo de la punta (eV) |

**Ejemplo:**

```bash
spmkit analyze scan.nid --output ./out --tip-wf 4.8
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
spmkit nanomech spec.nid --tip-radius 10e-9 --model sphere
```

Salida:

```
   Nanomecánica · curva 50/100 · sphere
┌──────────────────────┬───────────────┐
│ Parámetro            │         Valor │
├──────────────────────┼───────────────┤
│ Módulo de Young      │     26.13 MPa │
│ Punto de contacto    │     -12.45 nm │
│ Adhesión             │     -3.21 nN  │
│ RMSE                 │   1.234e-11   │
└──────────────────────┴───────────────┘
```

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
| `FOLDER` | Carpeta con archivos `.nid`, `.nhf` o `.gwy` |

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
| `--output`, `-o` | `figure.png` | Archivo de salida (`.png`, `.svg`, `.pdf`) |
| `--colormap` | `batlow` | Colormap (colormaps Crameri disponibles) |
| `--title` | (nombre del canal) | Título de la figura |

**Ejemplo:**

```bash
spmkit figure scan.nid -c Z-Axis -o topografia.svg --colormap tokyo
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

**Ejemplo:**

```bash
spmkit psd scan.nid -c Z-Axis
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
spmkit gui
```

!!! tip
    Si ves `ImportError`, instala el extra: `pip install "spmkit[gui]"`

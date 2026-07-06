# Roadmap — spmkit multi-física & Fathom (AFM)

> Spec del plan *long-shot*. Documento vivo: cada fase deriva su propio plan de
> implementación (`writing-plans`) → build → tests → PR verde → merge.

## 1. Visión (el norte)

Un ecosistema **modular, testeado y future-proof** para microscopía de sonda de barrido:

- **`spmkit`** — el *host* multi-física: modelos de datos, registries y la maquinaria
  común (I/O, pipeline, export, report). No asume un dominio.
- **Fathom** — la **extensión de AFM / espectroscopía de fuerza** sobre `spmkit`
  (curvas de fuerza mejor que Nanosurf ANA y JPK Data Processing, mapas de
  force-volume, análisis de imagen). En el futuro, **otros cores de otra física** se
  enchufan como extensiones hermanas, sin tocar el host.

Una sola aplicación de escritorio (el workspace Fathom) reemplaza a la app clásica de
7 pestañas; lee muchos formatos, cada uno **validado contra archivos reales**.

## 2. Principios de arquitectura (no negociables)

1. **Separación quirúrgica de 3 capas.** `core/` es Python puro **sin imports de UI**;
   `cli/` y `gui/` sólo orquestan/presentan e importan la API pública de `core`. Esta
   regla se preserva en cada fase — es lo que mantiene el repo limpio y modular.
2. **Registries pluggables** en vez de `if/elif` cableados. Todo punto de variación es
   un registro con descubrimiento: lectores I/O, operaciones de pipeline (ya existe),
   propiedades de mapa, **modelos de contacto**, paneles/perspectivas, plantillas de
   informe, y **dominios/extensiones**.
3. **Capacidades declaradas.** Un lector declara qué produce (`image` / `force` /
   `spectroscopy`); `load_any` rutea y la GUI abre la perspectiva correcta.
4. **Core testeable y revalidado.** Toda física vive en `core` con tests. Al reusar
   código validado en una fase nueva, **se revalida** (no se asume).
5. **Física honesta.** Modelos sin validación independiente se **construyen pero se
   marcan como experimentales** (flag en core + UI), nunca se presentan como
   publication-grade hasta revalidarlos.
6. **No-acoplamiento como código.** Un test de arquitectura (`tests/test_architecture.py`)
   + `ruff` banned-api prohíben importar `PyQt6`/`PySide6`/`pyqtgraph` dentro de `core/`.
   La regla no depende de disciplina humana: CI la hace fallar.
7. **API pública estable y versionada.** El contrato de plugins es `spmkit.plugins.v1`
   (Protocols). Cambios incompatibles → `v2` con compatibilidad hacia atrás; nunca se
   rompe la firma de `load_any`/registries sin bump de versión (protege extensiones de
   terceros — como los drivers de Napalm o las extensiones de VS Code).

## 3. Framework de extensiones (la pieza future-proof)

Los contratos son **`typing.Protocol`s versionados** en `core/plugins/contracts.py`
(grupo de entry-points **`spmkit.plugins.v1`**). Firmas clave:

```python
class DatasetInfo(Protocol):     # metadatos SIN cargar datos pesados
    kinds: tuple[Kind, ...]      # p.ej. ("image", "force") — un .spm QI es ambos
    channels: tuple[str, ...]
    grid_shape: tuple[int, int] | None

class Reader(Protocol):
    extensions: tuple[str, ...]
    def inspect(self, path) -> DatasetInfo: ...      # barato: solo cabecera
    def load(self, path, kind: Kind | None = None): ...  # carga perezosa del kind pedido

class Domain(Protocol):          # una física completa (Fathom = AFM)
    name: str
    readers: tuple[Reader, ...]
    analyses: tuple[Analysis, ...]
    perspectives: tuple[str, ...]
```

`load_any(path)` primero hace `inspect` (rápido), la GUI **pregunta al lector "¿qué hay
aquí?"** y —si hay varios `kind`— ofrece abrir como *Imagen* o *Mapa de curvas* **antes**
de cargar los megabytes. Registry en proceso para:

| Punto de extensión | Registra | Ejemplo Fathom |
|---|---|---|
| `readers` | lector de archivo + capacidades | `.jpk-force`, `.nid`, `.spm`, `.ibw` |
| `analyses` | operación de pipeline / analizador | Hertz, DMT, JKR, rugosidad |
| `contact_models` | modelo de contacto (exponente + E*) | sphere, cone, dmt, **jkr** |
| `map_properties` | propiedad mapeable de force-volume | módulo, adhesión, disipación |
| `panels` / `perspectives` | panel MVVM + perspectiva | curva, mapa, batch, imagen |
| `report_templates` | plantilla de informe | HTML/LaTeX de fuerza |
| **`domains`** | **una extensión de dominio completa** (su set de lo anterior) | **Fathom (AFM)** |

Regla de oro: **el host no conoce los dominios**; los dominios se auto-registran. Añadir
otra física = un paquete que registra su `domain` con sus lectores/análisis/paneles, sin
modificar `spmkit` ni Fathom.

## 4. Fases

Cada fase: spec breve → plan → build → tests (unit + validación contra archivos reales)
→ `ruff`/`black`/`mypy`/CI verde → PR → merge. Investigación de formatos/URLs delegada a
**agentes con modelo barato (haiku)** en paralelo; diseño, física e integración en Opus.

### F1 — Plataforma de formatos (la base) · ✅ *hecho*
- `core/plugins/contracts.py`: los **Protocols versionados** (`Reader`/`DatasetInfo`/
  `Analysis`/`Domain`) — **se escriben primero**, todo lo demás depende de ellos.
- `core/io/registry.py` v2: registry de lectores **con capacidades** + `inspect()`;
  `load_any(path, kind=None)` que **inspecciona antes de cargar** y soporta múltiples
  `kind` por archivo (QI = imagen + force).
- **Arnés de datos de prueba**: `scripts/fetch_samples.py` descarga samples open-source
  por formato a `reference/` (gitignored, **nunca commiteado**), con **fallback a assets
  pequeños offline** (1–2 por formato, vía GitHub Release o mínimos generados) para que
  el CI valide formato **sin red**. Tests con `skipif`-missing.
- Lectores nuevos (incrementales, cada uno con su validación):
  `.spm`/`.pfc` (Bruker/NanoScope, imagen + force-volume/QI), `.ibw` (Asylum),
  Park, HDF5 genérico; **`afmformats`** como backend opcional (extra `afm`) para la cola
  larga de formatos de curvas de fuerza.
- Revalidar `.nid`/`.jpk-force` existentes + **probar contra los JPK nuevos del lab**.
- **No rompe** la separación core/cli/gui.

### F2 — Unificar la app (retiro de la clásica, con legacy conservada)
- Migrar imagen/figura/3D/simulador a **perspectivas MVVM** de Fathom (View↔ViewModel↔core).
- Mover `main_window.py` + `*_tab.py` a **`src/spmkit/gui/legacy/`** — **documentado y
  conservado** (fallback limpio), con un comando `spmkit gui --legacy`. No se borra.
- Traer lo ya hecho: anotaciones de figura personalizables, Vista 3D en nm/µm.
- **`.spmproj` mínimo desde el día 1 de la nueva UI**: guarda archivos abiertos + receta
  activa (el estado analítico básico). El versionado de layouts de dock y preferencias
  complejas espera a F4.
- La UI **no** se acopla al core (separación quirúrgica).

### F3 — Profundidad de análisis (imagen completa + física avanzada)
- **Paridad completa de imagen** en Fathom reusando core validado (**revalidado**):
  grains, espectral, perfiles, correcciones/nivelado.
- **JKR y viscoelástico**: se **construyen** con su mejor formulación; si no se validan
  contra referencia independiente (dataset publicado / `nanite`/`afmfit`), quedan
  **flagged como experimentales** (no se retiran) para revalidar al conseguir archivos.
- Pruebas contra JPK nuevos + samples open-source descargados.

### F4 — Extensibilidad
- Sistema de **plugins** vía entry-points (readers/analyses/panels) + el registry de §3.
- **Endpoints para dominios/otros cores** (multi-física): contrato de `domain`.
- **`.spmproj`**: proyecto versionado (referencias a datos + recetas + layout).
- Layouts guardables, editor de tema/atajos, i18n.

### F5 — Pulido y release
- Docs (mkdocs), ejemplos por formato, empaquetado, versión. Migrar `docs/design/*` a
  la doc pública.

## 5. Estrategia de datos de prueba

- **Fuentes open-source**: samples de Gwyddion, datos de test de `afmformats`, demos
  públicas de Bruker/Asylum. URLs resueltas por agentes de investigación (haiku).
- **Resiliencia offline (crítico):** depender solo de URLs externas es frágil (mueren,
  caen). Se conservan **1–2 archivos pequeños por formato** como assets estáticos
  (GitHub Release del repo, o mínimos generados/base64) para que los tests básicos de
  formato corran **sin red**. `fetch_samples.py` prefiere el cache local; la red es
  el último recurso.
- **Ubicación**: `reference/` (gitignored). Un `scripts/fetch_samples.py` los baja bajo
  demanda; los tests hacen `pytest.importorskip`/`skipif(not path.exists())`.
- **Archivos del lab**: los `.nid` y **JPK nuevos** ya presentes en `reference/` — se
  usan para validación adicional, nunca se commitean.
- **CI** sigue en verde sin estos archivos (todos los tests que los usan son skippables).

## 6. Legacy

La app clásica no desaparece: se conserva en `gui/legacy/` con su documentación, y
`spmkit gui --legacy` la lanza. Fathom (`spmkit gui` / `spmkit workspace`) es el default.

## 7. Definición de "listo" por fase

Verde en `ruff` + `black` + `mypy src`; tests unit + validación; PR con CI verde y merge;
CHANGELOG y docs actualizados; sin acoplar UI↔core.

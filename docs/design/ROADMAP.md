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

## 3. Framework de extensiones (la pieza future-proof)

`spmkit` expone **entry-points** (grupo `spmkit.plugins`) y un registry en proceso para:

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

### F1 — Plataforma de formatos (la base) · *en curso*
- `core/io/registry.py` v2: registry de lectores **con capacidades**; `load_any(path)`
  unificado que devuelve `(dato, kind)`.
- **Arnés de datos de prueba**: script que descarga samples open-source por formato a
  `reference/` (gitignored, **nunca commiteado**); tests con `skipif`-missing.
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

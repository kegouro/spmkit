# Diseño: spmkit como reemplazo de Nanosurf ANA + JPK Data Processing (curvas de fuerza)

> Documento de arquitectura y plan de evolución. Estado: **propuesta** (v2, 2026-07).
> Objetivo estratégico: no clonar Gwyddion (imágenes), sino **superar el análisis de
> curvas de fuerza** de Nanosurf ANA y JPK/Bruker *Data Processing 8.1*.
>
> **v2** incorpora la revisión de diseño: estado de calibración explícito, lazy loading de
> force-volumes, ejecución paralela, pipeline con condiciones seguras, modelos viscoelásticos,
> incertidumbre Monte Carlo y API Jupyter/headless de primera clase. Detalle en §15.

---

## 1. Objetivo y alcance

El profesor quiere reemplazar dos herramientas de análisis **offline**:

- **Nanosurf ANA** — análisis de datos de instrumentos Nanosurf (`.nid`/`.nhf`).
- **JPK/Bruker SPM Data Processing 8.1** — análisis de curvas de fuerza y force-maps
  de instrumentos NanoWizard (`.jpk-force`, `.jpk-force-map`, `.jpk-qi-data`).

Ambos comparten un mismo núcleo funcional: **espectroscopía de fuerza** (force curves,
force spectroscopy). spmkit ya lee `.nid` a precisión de máquina y tiene un ajuste Hertz
básico; falta el resto del flujo profesional. Este documento define **cómo llegar ahí sin
romper la arquitectura de 3 capas** (`core` puro / `cli` / `gui`).

Fuera de alcance (por ahora): control del instrumento / adquisición. spmkit es análisis
offline, igual que ANA y JPK Data Processing.

---

## 2. Qué hacen ANA / JPK que spmkit todavía no

Mapeado contra el manual *NanoWizard Series User Manual 8.1* (§6 Force Spectroscopy,
§7 Calibration) y el *BioAFM Handbook 8.1* (§6 Force spectroscopy, §7 Cantilevers).

| Capacidad | JPK / ANA | spmkit hoy | Brecha |
|---|---|---|---|
| Segmentos extend/retract (+ pausa) | ✅ | ❌ (1 fila = 1 curva) | **crítica** |
| Canales crudos: height, (v)deflection, tiempo | ✅ | ❌ (solo z, force) | **crítica** |
| Calibración: InvOLS (sensibilidad) | ✅ | ❌ | **crítica** |
| Calibración: k por ruido térmico / Sader / contacto | ✅ | parcial (equipartición cruda) | alta |
| Separación punta-muestra (`sep = height − deflexión`) | ✅ | aprox. cruda | alta |
| Corrección de línea base (offset + tilt) | ✅ | offset+tilt (1 curva) | ok |
| Detección de contacto robusta | ✅ (varios métodos) | ✅ (threshold + RoV, recién añadido) | ok |
| Modelos: Hertz, Sneddon, DMT | ✅ | ✅ (recién añadido) | ok |
| Modelos: JKR, Oliver-Pharr, bottom-effect | ✅ | ❌ | media |
| Adhesión y **energía de disipación** (histéresis) | ✅ | solo pull-off | media |
| Detección de eventos de ruptura + WLC/FJC (single-molecule) | ✅ | ❌ | media |
| Incertidumbre y bondad de ajuste (σ, R²) | ✅ | ✅ (recién añadido) | ok |
| **Pipeline de procesamiento apilable y reproducible** | ✅ (Analysis Pipeline) | ❌ | **estratégica** |
| Force-volume / QI maps → mapas de propiedades | ✅ | parcial (`fit_all`) | alta |
| Histogramas/distribuciones batch (E, adhesión) con ajuste | ✅ | ❌ | media |
| Lectura `.jpk-force*` | ✅ (nativo) | ❌ | alta |
| Provenance / trazabilidad de cada resultado | parcial | ❌ | estratégica |

**Lectura clave:** la diferencia decisiva no es "más modelos". Es que ANA/JPK organizan
todo como un **pipeline de operaciones reproducible sobre segmentos calibrados**. Esa es la
pieza que hay que construir; los modelos cuelgan de ahí.

---

## 3. Principios de diseño

1. **Respetar la regla de oro**: `core` sin UI; `cli`/`gui` solo orquestan. Todo lo nuevo
   de física vive en `core/`.
2. **El pipeline es la columna vertebral**, no una feature más. Curva única, force-map y
   batch corren el **mismo** `Recipe`. La GUI graba las acciones del usuario como `Recipe`.
3. **Inmutabilidad y unidades explícitas** (como el modelo actual): cada dataclass congelada,
   cada cantidad con su unidad documentada.
4. **Compatibilidad hacia atrás**: `ForceCurve.z`/`.force` siguen funcionando; el modelo nuevo
   los deriva. No rompemos `fit_hertz` ni los tests actuales.
5. **Crecer por fases verificables**: cada fase entra con tests known-answer y sin romper CI.

---

## 4. Evolución del modelo de datos — `core/models/force.py` (NUEVO)

El corazón del cambio. Reemplaza el `ForceCurve` plano por un modelo con segmentos y
canales crudos, calibrable.

```python
#: Estado de calibración de un segmento (evita doble-InvOLS / fuerza sin calibrar).
#   "raw_v"        → señal cruda (V), sin calibrar
#   "deflection_m" → deflexión en metros (InvOLS aplicado)
#   "force_n"      → fuerza en newtons (k aplicado); listo para ajustar
CalState = Literal["raw_v", "deflection_m", "force_n"]


@dataclass(frozen=True)
class ForceSegment:
    """Un segmento de una curva de fuerza (extend / retract / pause / modulation).

    Guarda SIEMPRE los canales crudos (para poder recalibrar) y, a medida que el
    pipeline avanza, los derivados. ``state`` dice hasta dónde se calibró.
    """
    segment_type: str                     # "extend" | "retract" | "pause" | "modulation"
    direction: str                        # "approach" | "retract" | "static"
    raw_height: np.ndarray                # altura del piezo/medida (m)
    raw_deflection: np.ndarray            # señal cruda (V) o m si el archivo ya viene calibrado
    time: np.ndarray | None = None        # tiempo (s): loading rate, viscoelasticidad
    cycle: int = 0                        # índice de ciclo (curvas multi-ciclo)
    state: CalState = "raw_v"
    # Derivados que rellena el pipeline (None hasta que la op correspondiente corre):
    deflection: np.ndarray | None = None  # m, tras InvOLS
    force: np.ndarray | None = None       # N, tras k
    separation: np.ndarray | None = None  # m, tras height − deflexión

    def require_force(self) -> np.ndarray:
        """Devuelve la fuerza o lanza un error controlado si no se ha calibrado."""
        if self.force is None:
            raise ValueError(
                "Segmento sin fuerza calibrada (state="
                f"{self.state!r}); corre 'calibrate' antes de 'fit_elasticity'."
            )
        return self.force


@dataclass(frozen=True)
class ForceCurve:                     # reemplaza al actual (con shim de compatibilidad)
    """Una curva de fuerza completa: uno o más segmentos, más calibración y posición."""
    segments: tuple[ForceSegment, ...]
    calibration: "Calibration | None" = None
    position: tuple[float, float] | None = None   # (x, y) en m, para force-maps
    index: int = 0
    metadata: dict = field(default_factory=dict)

    def segment(self, kind: str, cycle: int = 0) -> ForceSegment | None: ...
    # --- shim de compatibilidad con el modelo viejo (extend) ---
    @property
    def z(self) -> np.ndarray: ...        # height del extend
    @property
    def force_legacy(self) -> np.ndarray: ...


@dataclass(frozen=True)
class ForceVolume:
    """Grilla de curvas de fuerza (force-map / QI) con carga perezosa.

    NO mantiene las curvas en RAM: un ``.jpk-force-map`` puede pesar GB. Guarda un
    índice y un ``loader`` que lee la curva N bajo demanda (con caché LRU). Para
    ``.nid`` (curvas chicas) el loader es trivialmente in-memory.
    """
    loader: "Callable[[int], ForceCurve]"     # lee la curva N bajo demanda
    n_curves: int
    grid_shape: tuple[int, int]               # (rows, cols)
    x_range: float                            # m
    y_range: float                            # m
    metadata: dict = field(default_factory=dict)

    def curve(self, index: int) -> ForceCurve:
        """Lee (perezosamente, con caché) la curva ``index``."""
        ...
```

**Migración segura:** `mechanics.extract_curves()` pasa a construir `ForceCurve` con un solo
segmento `extend` cuando el `.nid` no distingue trazas, y con `extend`+`retract` cuando sí.
El `fit_hertz` actual sigue aceptando el `ForceCurve` (usa el segmento `extend`). Los tests
existentes no cambian.

**Estado de calibración:** solo la operación `calibrate` del pipeline puede pasar un segmento
de `raw_v` → `deflection_m` → `force_n`. Las demás operaciones validan el `state` que necesitan
(p. ej. `fit_elasticity` exige `force_n` vía `require_force()`). Esto cierra el riesgo de aplicar
InvOLS dos veces o ajustar sin calibrar. Se eligió un `state` explícito en vez de `pint`/
`astropy.units` para no cargar el `core` con una dependencia de unidades (hoy solo numpy).

---

## 5. Subsistema de calibración — `core/analysis/calibration.py` (NUEVO)

Convierte señal cruda (V) → deflexión (m) → fuerza (N). Es lo primero que hace cualquier
analista en ANA/JPK y hoy no existe.

```python
@dataclass(frozen=True)
class Calibration:
    invols: float           # sensibilidad de deflexión, m/V (a.k.a. deflection sensitivity)
    spring_constant: float  # k, N/m
    method: str             # "thermal" | "sader" | "contact" | "manual"
    temperature: float = 293.15
    provenance: dict = field(default_factory=dict)

def deflection_sensitivity(hard_contact: ForceSegment) -> float:
    """InvOLS = pendiente del contacto sobre sustrato rígido (m/V)."""

def spring_constant_thermal(psd_freq, psd_amp, *, temperature=293.15,
                            correction_factor=0.817) -> float:
    """Ruido térmico: área del pico de resonancia → ⟨x²⟩ → k = χ·k_BT/⟨x²⟩ (Butt-Jaschke)."""

def spring_constant_sader(f0, q_factor, width, length, *, fluid="air") -> float:
    """Método de Sader (geometría + f0 + Q), sin tocar la muestra."""
```

`thermal_spring_constant` (hoy en `mechanics.py`) se **mueve** aquí y se generaliza; se deja
un alias en `mechanics` por compatibilidad. El factor χ de Butt-Jaschke ya lo añadimos.

---

## 6. El motor de Pipeline — `core/pipeline/` (NUEVO, pieza maestra)

Equivale a la **Analysis Pipeline** de JPK (manual §6.1.3). Una lista ordenada, serializable
y reproducible de operaciones que corre igual sobre una curva, un force-map o un batch.

```
core/pipeline/
├── __init__.py
├── operations.py     # registro nombre → función; cada op: (ForceCurve, **params) → ForceCurve|Result
├── recipe.py         # Recipe: lista ordenada de (op, params); to_yaml/from_yaml
└── run.py            # run(recipe, target) → resultado + provenance estampada
```

```python
@dataclass(frozen=True)
class Recipe:
    steps: tuple[tuple[str, dict], ...]     # [("baseline_correct", {...}), ("fit_elasticity", {...})]
    def to_yaml(self) -> str: ...
    @classmethod
    def from_yaml(cls, text: str) -> "Recipe": ...

# Operaciones registradas (todas puras, en core):
#   calibrate, baseline_correct, tip_sample_separation, smooth,
#   find_contact_point, fit_elasticity, detect_events, adhesion, dissipation
```

**Por qué desbloquea todo con poco código:**
- `core/batch.py` deja de estar hardcodeado a "roughness+KPFM en Z-Axis/CPD" → corre cualquier `Recipe`.
- La GUI **graba** lo que el usuario hace como un `.recipe.yaml` compartible/versionable.
- Es la unidad de **reproducibilidad** y el portador natural de **provenance**.
- Un force-map = correr el mismo `Recipe` por píxel.

---

## 7. Modelos de contacto y eventos

**`core/analysis/mechanics.py` (EXTENDER):** ya tiene Hertz/paraboloide/cono/DMT + σ/R² + RoV.
Añadir:
- `jkr` (Johnson-Kendall-Roberts): relación paramétrica implícita fuerza-indentación (adhesión fuerte, muestras blandas).
- `oliver_pharr`: rigidez de contacto de la pendiente de descarga (materiales duros).
- `bottom_effect`: corrección de sustrato rígido para muestras delgadas (Dimitriadis).

**`core/analysis/events.py` (NUEVO):** detección de eventos de ruptura en el retract y ajuste
de polímeros para single-molecule force spectroscopy:
- `detect_ruptures(retract) -> list[RuptureEvent]` (saltos de fuerza).
- `fit_wlc(event) / fit_fjc(event)` → longitud de contorno, fuerza de ruptura, loading rate.
- Histograma de fuerzas de ruptura (batch).

---

## 8. Force-volume / mapas — `core/analysis/forcevolume.py` (NUEVO)

Reemplaza y generaliza `mechanics.fit_all`. Corre un `Recipe` por píxel y arma mapas:
- Mapas: módulo E, adhesión, altura de contacto, disipación, pendiente de contacto.
- ROI/máscara para excluir zonas o medir sobre una región.
- Estadística batch: histogramas de E/adhesión con ajuste gaussiano/log-normal.
- Selección de píxel ↔ curva (para la UI: clic en el mapa muestra la curva).

---

## 9. Lectores — `core/io/`

- **`jpk.py` (NUEVO):** `.jpk-force`, `.jpk-force-map`, `.jpk-qi-data`. Son archivos ZIP con
  cabeceras `.properties` + segmentos binarios. Devuelven `ForceCurve`/`ForceVolume`.
  Registrar en `registry.py` (`_PARSERS`). Añadir test de validación con un archivo sintético.
- **`.nid` espectroscopía (MEJORAR `nid.py`):** hoy trata cada fila como curva plana. Detectar
  trazas extend/retract (por `Frame`/dirección) y construir `ForceCurve` con segmentos.
- **`.jpk-qi-image` / imágenes:** ya cubierto por el modelo de imagen existente.

---

## 10. Provenance y exportación

Cada export (HDF5/CSV/JSON/reporte) estampa: versión de spmkit, timestamp UTC, hash del
archivo fuente, la `Recipe` aplicada, y la `Calibration`. Nuevo comando `spmkit crate` empaqueta
datos + recipe + resultados (estilo RO-Crate) para reproducibilidad FAIR. Esto ataca la brecha
"provenance" que ni ANA ni JPK cubren bien → diferenciador real ante universidades.

---

## 11. Rediseño de UI — de 7 pestañas planas a un *workspace* por flujo

**Problema actual:** 7 pestañas desconectadas (Visor, Nanomecánica, Vista 3D, Resonancia,
Simulador, Editor, Comparar), cada una un form estático, todo en el hilo de UI (se congela).
No refleja el flujo de trabajo de un analista.

**Nuevo modelo:** un **workspace por perspectivas** que imita el flujo de ANA/JPK:

```
Cargar → Calibrar → Pipeline de procesamiento → Ajustar → Mapa/Batch → Exportar
```

### Layout (perspectiva "Curva de fuerza")

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Toolbar:  Abrir · Perspectiva[Curva|Mapa|Imagen] · Recipe▾ · Export · Tema │
├───────────────┬──────────────────────────────────────┬─────────────────────┤
│ NAVEGADOR     │            LIENZO DE CURVA            │  PIPELINE (apilable) │
│ (izquierda)   │            (centro)                   │  (derecha)           │
│               │                                       │                      │
│ ▸ archivo.jpk │   extend ─ (azul)  retract ─ (naranjo)│  ✓ Calibración       │
│   ▸ curva 0   │   ● punto de contacto                 │     InvOLS · k        │
│   ▸ curva 1 ◄ │   ─ ajuste (Hertz/DMT/JKR)            │  ✓ Línea base        │
│   ...         │   ▲ eventos de ruptura                │  ✓ Contacto (RoV)     │
│ [mapa QI 🔲]  │                                       │  ✓ Ajuste elasticidad│
│  (clic=curva) │   [scrubber de curvas ◄════▶ ]        │  + Añadir paso ▾     │
│               │                                       │  ── Resultados ──     │
│               │                                       │  E = 4.5 ± 0.1 MPa    │
│               │                                       │  R² = 0.999 · adh …   │
├───────────────┴──────────────────────────────────────┴─────────────────────┤
│ DOCK inferior:  Mapas de propiedades · Histogramas (E, adhesión) · Tabla batch │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Perspectivas** (no pestañas planas): "Curva" (análisis profundo de 1 curva), "Mapa"
  (force-volume, mapas + histogramas), "Imagen" (el visor de topografía actual). Comparten
  panel de pipeline y navegador. El Simulador y Resonancia pasan a ser perspectivas/plugins
  secundarios.
- **Pipeline panel = la Analysis Pipeline de JPK**: pasos apilables, reordenables (drag),
  activables, con parámetros editables. Es la misma `Recipe` del core → lo que ves es lo que
  se guarda y se reproduce.
- **Threading obligatorio**: `fit_all`, force-maps, reportes y carga corren en `QThreadPool`
  con barra de progreso cancelable. Se acaba el congelamiento (brecha que marcó la auditoría).
- **Sesión guardable**: `.spmproj` con archivos cargados, recipe, calibración y layout.

### Reestructuración de `gui/` (rehacer, reutilizando lo que sirve)

```
gui/
├── app.py                      # entrypoint (se conserva)
├── workspace.py                # NUEVO shell: navegador + centro + pipeline + dock inferior
├── perspectives/
│   ├── curve.py                # NUEVO: perspectiva Curva (reemplaza nanomech_tab)
│   ├── map.py                  # NUEVO: perspectiva Mapa (force-volume)
│   └── image.py                # adapta viewer_tab actual
├── widgets/
│   ├── force_canvas.py         # NUEVO: lienzo pyqtgraph con segmentos/ajuste/eventos
│   ├── pipeline_panel.py       # NUEVO: la Analysis Pipeline (edita Recipe del core)
│   ├── calibration_panel.py    # NUEVO: InvOLS + k (thermal/Sader)
│   ├── data_browser.py         # NUEVO: árbol archivos→curvas + thumbnail de mapa
│   ├── mpl_canvas.py           # NUEVO base: extrae el boilerplate matplotlib duplicado en 6 tabs
│   └── background.py           # NUEVO: helper QThreadPool + QProgressDialog
├── theme.py                    # se conserva (aplicar mpl_style de verdad)
└── figure_tab.py, compare_tab.py, view3d_tab.py, simulator_tab.py, resonance_tab.py
                                # se conservan como perspectivas/paneles secundarios, migran gradual
```

---

## 12. Mapa de archivos (rutas exactas)

**Nuevos (core):**
- `src/spmkit/core/models/force.py` — `ForceSegment`, `ForceCurve`, `ForceVolume`.
- `src/spmkit/core/analysis/calibration.py` — InvOLS, k (thermal/Sader), `Calibration`.
- `src/spmkit/core/analysis/events.py` — ruptura, WLC/FJC.
- `src/spmkit/core/analysis/forcevolume.py` — mapas + batch stats.
- `src/spmkit/core/pipeline/{__init__,operations,recipe,run}.py` — el motor de Recipe.
- `src/spmkit/core/io/jpk.py` — lectores `.jpk-force*`.

**Modificados (core):**
- `src/spmkit/core/analysis/mechanics.py` — + JKR, Oliver-Pharr, bottom-effect; usar el nuevo modelo.
- `src/spmkit/core/io/nid.py` — construir segmentos extend/retract en espectroscopía.
- `src/spmkit/core/io/registry.py` — registrar `jpk`.
- `src/spmkit/core/batch.py` — ejecutar `Recipe` en vez de análisis hardcodeado.
- `src/spmkit/core/export/writers.py` — estampar provenance + recipe + calibración.
- `src/spmkit/core/models/__init__.py`, `core/analysis/__init__.py` — exports públicos.

**Nuevos/rehechos (gui):** ver §11.

**Nuevos (cli):**
- `spmkit calibrate`, `spmkit fit` (con `--model jkr|oliver-pharr`), `spmkit fmap`,
  `spmkit recipe run <recipe.yaml> <archivo>`, `spmkit crate`.

**Tests:** un `tests/core/test_pipeline.py`, `test_calibration.py`, `test_events.py`,
`test_forcevolume.py`, `test_io_jpk.py`, y validación con archivos sintéticos.

---

## 13. Roadmap por fases (incremental y verificable)

| Fase | Entrega | Verificación |
|---|---|---|
| **0. Credibilidad** (casi listo) | Fuga de privacidad saneada ✅, release limpio 0.1.3, badges dinámicos | CI verde, tag == versión |
| **0.5. Spike JPK** (NUEVO) | 2–3 días: abrir un `.jpk-force` en Python, leer 1 segmento y sus factores de escala. NO escribir el lector completo. | Se extraen arrays crudos de una curva real |
| **1. Modelo + calibración** | `force.py` (segmentos con `state` de calibración + interfaz de **lazy loading** para `ForceVolume`), `calibration.py` (InvOLS, k thermal/Sader), separación punta-muestra. Shim de compatibilidad. | Known-answer InvOLS/k; guardas de `state`; tests actuales intactos |
| **2. Pipeline (keystone)** | `core/pipeline/` (Recipe con **condiciones seguras**, operations, run con **ejecución paralela** stdlib+opcional joblib), `batch.py` genérico | Recipe roundtrip YAML; batch corre recipe; paralelo == secuencial |
| **3. Modelos + viscoelasticidad** | JKR, Oliver-Pharr, bottom-effect; **modelos viscoelásticos** (relajación/creep/SLS); **incertidumbre Monte Carlo** (propaga InvOLS+k); disipación/adhesión-energía. *(WLC/FJC → Fase 7)* | Known-answer por modelo; MC da σ física; SLS recupera τ |
| **4. Lectores JPK** | `io/jpk.py` (.jpk-force/-map/-qi con lazy loading), `.nid` con segmentos | Validación con archivo sintético + real |
| **5. Force-volume + batch** | `forcevolume.py` (mapas por píxel en paralelo, ROI, histogramas con ajuste) | Mapa recupera E conocido; histograma |
| **6. UI workspace** | `gui/workspace.py` + perspectivas + pipeline panel + threading; lienzo **pyqtgraph** (scrubbing de 10k curvas a 60 fps) | Smoke test GUI headless; no congela |
| **7. Provenance + comunidad + single-molecule** | Exports con recipe/hash, `spmkit crate` (RO-Crate/FAIR), plugin entry-points, `events.py` (ruptura, WLC/FJC), docs/notebooks | Roundtrip provenance; WLC recupera Lc; plugin de ejemplo |

Recomendación de orden: **0.5 → 1 → 2 → 3** primero (el core de curvas de fuerza, que es lo
que tu profe quiere), luego **6** (UI) para el "wow" demostrable, y **4/5/7** después según qué
instrumentos haya que soportar.

---

## 14. Decisiones tomadas (2026-07-03)

1. **Formatos:** **Nanosurf `.nid` primero.** El lab es principalmente Nanosurf. Se prioriza
   mejorar la espectroscopía `.nid` (segmentos extend/retract) en Fase 1; el lector JPK
   (`.jpk-force*`) baja a Fase 4.
2. **UI:** **Rehacer limpio de una.** Se reemplaza la GUI entera por el nuevo `workspace.py`
   (no migración gradual). → Se hace en una rama dedicada, con smoke test headless antes de
   fusionar, para no dejar la app rota en `main`. Las pestañas viejas se retiran al cerrar la
   Fase 6.
3. **Formato de `Recipe`:** **YAML** (legible y editable a mano).
4. **Single-molecule (WLC/FJC):** **Después.** El foco inmediato es nanomecánica (módulo,
   adhesión, disipación, mapas). `events.py` y los ajustes WLC/FJC se mueven a una fase
   posterior (post-Fase 5), condicionados a que el lab haga unfolding/unbinding.

### Orden de ejecución acordado

`Fase 0.5 (spike JPK, 2-3 días)` → `Fase 1 (.nid con segmentos + calibración + lazy loading)` →
`Fase 2 (pipeline/Recipe + paralelo)` → `Fase 3 (JKR, Oliver-Pharr, bottom-effect,
viscoelástico, Monte Carlo — sin WLC/FJC)` → `Fase 5 (force-volume + batch)` →
`Fase 6 (UI rehecha, rama dedicada, pyqtgraph)` → `Fase 4 (lector JPK)` y
`Fase 7 (provenance + plugins + single-molecule)` al final.

---

## 15. Refinamientos tras revisión (v2)

Ajustes acordados en la revisión de diseño, con el razonamiento de cada decisión.

### 15.1 Estado de calibración explícito (§4)
Cada `ForceSegment` guarda su `state` (`raw_v` → `deflection_m` → `force_n`) y los canales
crudos (`raw_height`, `raw_deflection`) además de los derivados. Solo `calibrate` avanza el
estado; el resto de operaciones validan lo que necesitan (`require_force()`). Cierra el riesgo
de doble-InvOLS o de ajustar sin fuerza. **Sin `pint`/`astropy.units`**: se evita cargar el
`core` con una dependencia de unidades; un `state` + guardas logra lo mismo.

### 15.2 Lazy loading de force-volumes (§4, Fase 1)
`ForceVolume` no mantiene las curvas en RAM (un `.jpk-force-map` pesa GB). Guarda `n_curves`,
`grid_shape` y un `loader(index) -> ForceCurve` con caché LRU. La **interfaz** se diseña desde
la Fase 1 para no reescribir el modelo después; para `.nid` (curvas chicas) el loader es
in-memory trivial. Es la diferencia entre soportar mapas grandes o reventar la RAM.

### 15.3 Ejecución paralela del pipeline (§6, Fase 2)
El cómputo por curva es CPU-bound; el GIL serializa Python puro (aunque NumPy/SciPy lo liberen).
`run.py` sobre un `ForceVolume` usa `concurrent.futures.ProcessPoolExecutor` (stdlib, cero
dependencias) con *chunking* para amortizar el IPC. `joblib[loky]` queda como **extra opcional**
(`spmkit[parallel]`) para quien quiera su robustez/backends. El `Recipe` es serializable (YAML),
así que se envía a los workers sin problema.

### 15.4 Pipeline con condiciones seguras (§6, Fase 2)
Los pasos del `Recipe` admiten una `condition` (p. ej. correr `fit_elasticity` solo si se
detectó contacto). **No se usa `eval()`**: un `recipe.yaml` es un archivo externo y evaluar
strings arbitrarios es un hueco de seguridad. Se implementa un evaluador restringido —
comparaciones (`==`, `<`, `>`, `and`, `or`) sobre un conjunto de campos de resultado con lista
blanca (`contact_detected`, `r_squared`, `n_fit`, ...)—, no Python arbitrario.

```yaml
name: standard_nanoindentation
steps:
  - op: calibrate
    params: {invols: 50.0e-9, k: 0.2}   # o "from_metadata" para leerlos del archivo
  - op: correct_baseline
    params: {segment: extend, region: pre-contact}
  - op: find_contact_point
    params: {method: rov, threshold: 0.2}
  - op: fit_elasticity
    condition: "contact_detected and r_squared > 0.9"   # evaluador restringido, sin eval()
    params: {model: hertz, tip_radius: 20.0e-9, max_indentation: 50.0e-9}
```

### 15.5 Viscoelasticidad — el diferenciador real (§7, Fase 3)
JPK y ANA son flojos en viscoelasticidad; ahí spmkit los supera de verdad. En muestras blandas
(polímeros, células, hidrogeles) hay histéresis y dependencia con la tasa de carga que un modelo
elástico no captura. Se añaden modelos analíticos bien definidos: **relajación de esfuerzo**,
**fluencia/creep** y **Standard Linear Solid (SLS)** → módulos E₀/E∞ y tiempo de relajación τ.
Requiere el canal `time` y segmentos `pause`/`modulation` (por eso el modelo enriquecido de §4).
*Nota:* la librería "PyRhizome" mencionada en la revisión **no se pudo verificar** que exista;
se implementa propio (modelos cerrados) y se evalúa alguna librería de reología AFM como
referencia antes de reimplementar, no como dependencia a ciegas.

### 15.6 Incertidumbre Monte Carlo (§7, Fase 3) — publicable
`fit_elasticity` reporta σ del ajuste, pero eso ignora la incertidumbre física de InvOLS y de k.
Nuevo `fit_elasticity_mc()`: repite el ajuste N veces muestreando InvOLS y k dentro de sus
errores → un E con incertidumbre **física real**, no solo matemática. Es exactamente lo que
falta en JPK/ANA y lo que un referee valora.

### 15.7 API Jupyter/headless de primera clase (§10, elevado)
El `core` puro + `Recipe` en YAML hacen a spmkit *scriptable* — algo que ANA/JPK (cajas negras)
no ofrecen. Se expone una API de nivel superior:

```python
import spmkit
recipe  = spmkit.Recipe.from_yaml("mi_analisis.yaml")
results = spmkit.run(recipe, "experimento.nid")     # corre el pipeline
results.to_dataframe().to_csv("resultados.csv")     # pandas es extra opcional
```

`_repr_html_`/`_repr_png_` en `SPMChannel` y los `*Result` para render inline en notebooks.
`to_dataframe()` vive en un camino opcional (`spmkit[pandas]`) para no cargar el core. Mensaje
de marketing: *"JPK Data Processing, pero scriptable y reproducible."*

---

## 16. Detalles de implementación (v2.1) — "the devil is in the details"

Gotchas técnicos detectados en la segunda revisión, a respetar al escribir código.

### 16.1 Loaders picklables (multiprocessing + lazy loading)
`ProcessPoolExecutor` serializa con `pickle`, y **los `lambda`/closures no son picklables**;
un file handle abierto tampoco cruza a otro proceso. Por eso `ForceVolume.loader` **no** es una
función anónima sino una **instancia de clase picklable** que guarda solo la ruta (o las curvas,
para in-memory) e implementa `__call__`; cada worker abre su propio handle a partir de la ruta.
Se provee `InMemoryLoader` (dataclass congelada con las curvas) para `.nid`; los lectores de
archivos grandes usarán un `FileLoader(path, index_table)`. Esto mantiene stdlib viable y deja
`joblib` como extra opcional real, no obligatorio.

### 16.2 Origen dinámico de la calibración
La op `calibrate` resuelve `invols`/`k` dinámicamente: `"from_metadata"` los lee del `.nid`/
`.jpk` (varían por día o por curva si se calibró in-situ) y cae al valor explícito si no están.
Así el mismo `Recipe` sirve para un dataset completo, no solo un lote uniforme.

### 16.3 Semilla del Monte Carlo (determinismo en CI)
`fit_elasticity_mc` es estocástico → **debe** aceptar `seed` en su config YAML. Los tests fijan
la semilla (coherente con la convención del repo: todo RNG usa `np.random.default_rng(seed)`).
Sin esto, los known-answer de CI fallarían de forma intermitente.

### 16.4 Callback de progreso a través de procesos
`core/pipeline/run.py` acepta `progress: Callable[[float, str], None] | None`. El bucle que
consume el pool (en el **proceso principal**, vía `as_completed`) invoca el callback a medida
que llegan resultados; el wrapper de Qt lo traduce a un `pyqtSignal` hacia el hilo de UI. Así
`core` no depende de Qt y la barra de progreso avanza sin congelar la interfaz.

### 16.5 Regla de renderizado híbrido (pyqtgraph vs matplotlib)
- **pyqtgraph** para todo lo interactivo: lienzo de curvas, scrubbing de 10k curvas, mapas de
  propiedades en vivo (60 fps).
- **matplotlib** solo para el dock de histogramas/reportes y la **exportación final** de figuras
  de publicación (tipografía LaTeX, alta DPI). No se usa matplotlib en el camino interactivo.

### 16.6 Esquema del DataFrame de resultados (formato *long*)
`results.to_dataframe()` emite un esquema estándar y estable (para reemplazar a JPK y permitir
`df.plot.scatter(x="x", y="E")` directo):

```
columns = [curve_index, x, y, segment, cycle, model,
           E_Pa, E_err_Pa, r_squared, adhesion_N, dissipation_J,
           contact_point_m, n_fit]
```

Una fila por (curva × segmento ajustado). Unidades SI explícitas en el nombre de columna.

---

## 17. Resultado del spike JPK (Fase 0.5) — ✅ hecho

Se desempaquetaron curvas de fuerza JPK reales (dataset abierto **afmformats**,
`AFM-analysis/afmformats`). Muestras en `reference/jpk_samples/` (gitignored). Un
`.jpk-force`/`.jpk-force-map` es un **ZIP** con esta estructura:

```
header.properties                              # cabecera global
segments/0/segment-header.properties           # segmento 0 (extend)
segments/0/channels/height.dat                 # canales crudos (enteros)
segments/0/channels/vDeflection.dat
segments/0/channels/strainGaugeHeight.dat
segments/1/...                                 # segmento 1 (retract)
```

- **Segmentos**: `force-segment-header.name.name = extend-spm` / `retract-spm`;
  `num-points` por segmento. → mapea 1:1 a `ForceSegment` (§4).
- **Canales `.dat`**: enteros crudos, `data.type = short` (int16, big-endian JPK).
- **Conversión = cascada de "calibration slots"** (cada uno `offset + multiplier`):
  1. `encoder` (short → V): `multiplier`, `offset`.
  2. `conversion.distance` (V → m): `multiplier` = **InVOLS** (sensibilidad, m/V).
  3. `conversion.force` (m → N): `multiplier` = **constante de resorte k** (N/m).

  Ejemplo real del sample: InVOLS ≈ 7.0e-8 m/V, k ≈ 0.0435 N/m — **ambos vienen en
  el archivo** (confirma §16.2 `from_metadata`).

**Implicancia para el lector JPK (Fase 4):** `io/jpk.py` = `zipfile` + parseo de
`.properties` (INI-like `clave=valor`) + `np.frombuffer(dtype='>i2')` por canal +
aplicar la cascada de conversiones. La `Calibration` se lee directa de los slots
`distance`/`force`. El ecosistema `afmformats`/`nanite`/`PyJibe` (Paul Müller) sirve
de referencia de implementación (y de datos de test).
```

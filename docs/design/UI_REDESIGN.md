# Rediseño total de la UI de spmkit — "Instrumento"

> Documento de diseño e implementación. Estado: **propuesta v1** (2026-07).
> Objetivo: rehacer por completo la interfaz — elegante, moderna, dinámica,
> configurable, personalizable, expandible, modificable y **muy cómoda para
> maximizar el flujo de trabajo** — a nivel de herramienta que se presenta ante
> labs y universidades para reemplazar Nanosurf ANA y JPK Data Processing.

---

## 0. Dirección de diseño (el norte)

**Nombre de la estética: "Instrumento"** — *grafito de precisión con señal teal*.
Tono dominante: **Industrial / Utilitario** cruzado con **Editorial** (tipografía de
datos refinada). Un solo cruce, disciplinado.

**Puntuación DFII** (Design Feasibility & Impact Index):

| Dimensión | Puntaje | Razón |
|---|---|---|
| Impacto estético | 4 | El panel de pipeline vivo + el brushing ligado son memorables |
| Fit de contexto | 5 | Perfecto para reemplazar un instrumento científico |
| Factibilidad | 4 | PyQt6 + pyqtgraph lo permiten; docking/threading requieren rigor |
| Seguridad de rendimiento | 4 | pyqtgraph (GPU) + hilos; con disciplina se mantiene fluido |
| Riesgo de consistencia | −1 | Sistema de tokens + clase base de panel lo mantienen coherente |
| **DFII** | **15 (Excelente)** | **Ejecutar plenamente** |

**Ancla de diferenciación** — *"Si le quitas el logo, lo reconoces por…"*:
> el **panel de pipeline** que se re-ejecuta y previsualiza al editar; el **brushing
> ligado mapa↔curva** (pasas el cursor por un píxel y ves su curva; pintas un rango de
> módulo y se resaltan los píxeles); y los **readouts en monoespaciado tabular** con
> acento teal sobre grafito casi negro. Se siente como un **osciloscopio de
> laboratorio**, no como un dashboard SaaS.

**Anti-slop (lo que NO haremos):** ni gradientes morados de SaaS, ni Material/Bootstrap
por defecto, ni secciones simétricas predecibles, ni micro-animaciones decorativas por
todos lados, ni fuentes genéricas. El dato manda; la decoración sirve a la lectura.

**Qué se conserva del alma actual** (bien elegida por el autor): grafito casi negro /
papel cálido, **un** acento teal confiado, mono tabular para valores científicos,
stacks de fuente nativos. Lo elevamos a clase mundial; no lo tiramos.

---

## 1. Filosofía y principios

1. **El dato es el héroe.** El cromo (bordes, fondos, botones) retrocede; el heatmap,
   la curva y los números avanzan. Máximo "data-ink".
2. **Nada bloquea.** Cero congelamientos: todo cómputo pesado corre fuera del hilo de
   UI, con progreso cancelable. La app debe *sentirse* viva siempre.
3. **Reproducibilidad visible.** Cada resultado muestra la **receta** (`Recipe`) que lo
   produjo. La GUI *graba* lo que haces como un pipeline compartible.
4. **Teclado primero.** Todo accionable desde el teclado y una **paleta de comandos**
   (Cmd/Ctrl-K). El mouse es opcional, no obligatorio.
5. **Configurable sin tocar código.** Layouts, temas, atajos, colormaps y hasta paneles
   nuevos (plugins) se cambian desde la UI o archivos de config.
6. **Progresión suave.** Simple por defecto, poder a un clic. Sin muros de opciones.

---

## 2. Sistema de diseño (tokens)

Un único sistema de tokens alimenta QSS (Qt), pyqtgraph y matplotlib — así los gráficos
se sienten **nativos** del tema, no incrustados. Vive en `gui/design/tokens.py`.

### 2.1 Color

Historia de color dominante: **grafito** (superficie) + **teal** (señal) + **neutrales**.
El teal se usa SOLO para: estado activo, foco, la traza de datos primaria, y acciones
primarias. Nunca como relleno decorativo.

| Token | Dark | Light | Uso |
|---|---|---|---|
| `bg` | `#0B0E13` | `#F4F2EC` | Fondo raíz (grafito / papel cálido) |
| `surface` | `#121821` | `#FFFFFF` | Paneles |
| `surface-2` | `#171F2A` | `#ECE8DF` | Controles, barras, dock headers |
| `elevated` | `#1E2733` | `#E4DFD4` | Hover / menús / popovers |
| `overlay` | `rgba(6,9,13,.66)` | `rgba(20,18,12,.42)` | Modales, backdrop |
| `text` | `#E8EEF5` | `#181C22` | Texto primario |
| `text-muted` | `#93A0AE` | `#5A626B` | Secundario / hints |
| `text-faint` | `#5C6875` | `#8A8F98` | Deshabilitado / marcas de eje |
| `border` | `#232C38` | `#DBD6CB` | Divisorias hairline |
| `border-strong` | `#33404F` | `#C4BEB0` | Hover / activo |
| `accent` | `#2DD4BF` | `#0E9488` | Teal de señal |
| `accent-press` | `#14B8A6` | `#0B7C72` | Pressed |
| `accent-soft` | `#0F3A37` | `#CFEEE9` | Fondos de estado activo |
| `success` | `#4ADE80` | `#15803D` | R² bueno / OK |
| `warning` | `#FBBF24` | `#B45309` | Ajuste dudoso |
| `danger` | `#F87171` | `#B91C1C` | Error / fallo |

**Paleta de datos** (colorblind-safe, compartida por pyqtgraph y matplotlib):
- Secuencial (mapas): **batlow** (Crameri) por defecto; alternativas: viridis, roma,
  y el "gold" NanoSurf para topografía por familiaridad.
- Categórica (trazas): teal `#2DD4BF` (extend/primario), ámbar `#F59E0B` (retract),
  violeta `#A78BFA`, coral `#FB7185` — 4 tonos distinguibles en ambos modos.
- Divergente (residuos): vik (Crameri).

### 2.2 Tipografía

Dos roles, contraste estructural:
- **UI**: stack nativo refinado — `-apple-system, "SF Pro Text", "Segoe UI Variable",
  "Inter Tight", system-ui`. (Distintivo por peso y tracking, no por novedad.)
- **Dato numérico**: **mono tabular** — `"SF Mono", "JetBrains Mono", "Cascadia Code",
  "Menlo"`. Todos los números científicos, ejes y readouts en mono con cifras de ancho
  fijo: alinean en columnas como un instrumento real. **Este es un ancla de identidad.**

Escala (base 13px UI): `11 / 12 / 13 / 15 / 18 / 22 / 28`. Line-height 1.45 UI,
1.2 en readouts densos. Pesos: 400 y 500 (nunca 700 — pesa demasiado sobre grafito).

### 2.3 Espacio, radio, elevación

- Grilla de 4px. Espaciados: `4 / 8 / 12 / 16 / 24 / 32`.
- Radios: `6px` (controles), `10px` (paneles/cards), `14px` (modales). Sin radios en
  bordes de un solo lado.
- Elevación por **capa + borde**, no por sombras dramáticas: `surface` → `elevated` con
  `border` hairline; modales con `overlay` + sombra sutil `0 12px 40px rgba(0,0,0,.45)`.
- Densidad: dos modos, **Cómodo** (default) y **Compacto** (−2px en paddings, −1px
  fuente) — alterna con `Ctrl+Shift+D`. El compacto es para pantallas de lab pequeñas.

### 2.4 Movimiento

Con propósito, escaso, alto impacto. Nada de spam.
- Duraciones: `120ms` (hover/estado), `200ms` (paneles/perspectivas), `260ms`
  (entrada de vista). Easing: `cubic-bezier(.2,.8,.2,1)` (salida suave, "spring" leve).
- **Sí animan**: transición entre perspectivas (fundido + leve slide), skeleton
  shimmer mientras carga, el marcador de progreso, el resaltado de brushing.
- **NO animan** (crítico): los datos científicos al re-ajustar — el cambio de la curva
  o el mapa es **instantáneo** (verdad, no espectáculo). `prefers-reduced-motion`
  respetado: todo cae a fundidos de 80ms o nada.

### 2.5 Iconografía

Set lineal de 1.5px, esquinas redondeadas suaves, monocromo (heredan `text`/`accent`).
Preferir SVG propios ligeros; consistencia sobre cantidad. Iconos solo donde aceleran el
reconocimiento (herramientas, tipos de panel), nunca decorativos.

---

## 3. Arquitectura de la interfaz — Workspace de paneles + Perspectivas

Muere el modelo de **7 pestañas planas**. Nace un **workspace** único, tipo estación de
trabajo profesional (piensa Blender/DaVinci, pero calmo y científico):

- **Paneles acoplables** (dock) que se arrastran, apilan, flotan y se cierran.
- **Perspectivas**: presets de layout + paneles para una tarea. El usuario cambia de
  tarea, no de "pestaña". Perspectivas base:
  1. **Imagen** — topografía, rugosidad, perfiles, KPFM, granos, espectral, 3D.
  2. **Curva de fuerza** — la joya: una curva, calibración, pipeline, ajuste, inspector.
  3. **Force-volume / Mapa** — grilla de curvas → mapas de propiedades + brushing.
  4. **Batch** — carpeta → tabla + distribuciones + provenance.
  5. **Figura** — editor de figura de publicación.
  6. **Simulador / Enseñanza** — gemelo digital del cantiléver (modo docente).

### 3.1 Wireframe del shell

```
┌ spmkit ─────────────────────────────────────────────────────  ⌘K  ◐  ⚙ ─┐
│ ◱ Imagen  ◈ Curva  ▦ Mapa  ▤ Batch  ✦ Figura  ◐ Simulador      [rec ●]  │  ← barra de perspectivas + grabación de receta
├──────────────┬───────────────────────────────────────────────┬───────────┤
│  NAVEGADOR   │                LIENZO PRINCIPAL                │ INSPECTOR │
│  (dock izq)  │                (área central)                  │ (dock der)│
│              │                                                │           │
│  ▸ archivos  │        [heatmap / curva / mapa según           │  contexto │
│  ▸ curvas    │             la perspectiva activa]             │  del      │
│  ▸ canales   │                                                │  objeto   │
│              │                                                │  seleccio-│
│  [thumb map] │                                                │  nado     │
├──────────────┴───────────────────────────────────────────────┴───────────┤
│  DOCK INFERIOR:  Pipeline · Consola de resultados · Histogramas · Log     │
├───────────────────────────────────────────────────────────────────────────┤
│ status: archivo.jpk · k=0.043 N/m · 100 curvas · ▓▓▓▓░ 62% ajustando… ⨯   │  ← barra de estado + progreso cancelable
└───────────────────────────────────────────────────────────────────────────┘
```

Tres zonas de dock (izq/der/inferior) + centro. Todo redistribuible y **guardable como
layout con nombre**. La barra de perspectivas arriba; el botón `[rec ●]` **graba la
receta** de lo que haces.

---

## 4. El Pipeline Panel — la columna vertebral

Es la traducción visual del `Recipe` reproducible del core. **Lo que ves es lo que se
guarda y se reproduce.** Vive en el dock inferior o derecho.

```
┌ Pipeline · standard_dmt.recipe ────────────────  ▶ Correr  ⤓ Exportar YAML ─┐
│ ⣿ 1  Calibrar          InVOLS 50 nm/V · k 0.043 N/m        [desde archivo] ▾│
│ ⣿ 2  Línea base        región: sin contacto                                 │
│ ⣿ 3  Punto de contacto método: RoV                                          │
│ ⣿ 4  Ajuste elasticidad  ⟨si contacto⟩  Hertz · R=20nm · ν=0.3      E=4.5kPa│
│ ┄┄ + Añadir paso ▾  (calibrar · base · contacto · ajustar · eventos · …)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Pasos **arrastrables** (reordenar), **conmutables** (on/off), con parámetros inline y
  **condiciones** (`⟨si contacto⟩`) — el evaluador seguro del core, sin `eval`.
- Al editar un paso, el pipeline **se re-ejecuta al instante** sobre la curva activa y
  el lienzo se actualiza (preview vivo). Si el volumen es grande, corre solo la curva
  visible y ofrece "Aplicar a todo el mapa".
- `⤓ Exportar YAML` guarda la receta; `▶ Correr` la aplica al mapa/batch.
- **Grabar receta** (`[rec ●]` del shell): cada acción manual del usuario se registra
  como paso, produciendo una receta editable — sin escribir YAML a mano.

---

## 5. Perspectiva "Curva de fuerza" (el flujo joya)

Flujo end-to-end: **cargar → navegar → calibrar → construir pipeline → ajustar →
inspeccionar → (mapear) → exportar**, todo sin cambiar de ventana.

```
┌────────────┬──────────────────────────────────────────────┬──────────────────┐
│ NAVEGADOR  │              LIENZO DE CURVA                   │    INSPECTOR     │
│            │                                                │                  │
│ archivo ▸  │   fuerza(nN)                                   │  Ajuste          │
│  curva 0   │    ▲                          ╱ extend (teal)  │  ─────────────── │
│  curva 1◄  │    │           ╱fit─────      ╱                │  E   4.52 kPa    │
│  curva 2   │    │          ╱          ╲___╱ retract (ámbar) │  ± 0.11  R².998  │
│  ...       │    │   ● contacto                              │  adh   3.2 nN    │
│ [mapa QI]  │    │__╱________________________▶ separación    │  disip 2.8 fJ    │
│ (clic=curva)│   │  residuos: ░░▓░░▁▂▁░░  (banda 95%)        │  modelo Hertz    │
│            │   [◀ scrubber de curvas ▓▓▓░░░ 1/100 ▶]        │  ─────────────── │
│            │                                                │  provenance ▸    │
├────────────┴──────────────────────────────────────────────┴──────────────────┤
│  Pipeline: Calibrar · Base · Contacto(RoV) · Ajuste(Hertz)  ⟨preview vivo⟩    │
└───────────────────────────────────────────────────────────────────────────────┘
```

Detalles que dan comodidad:
- **Scrubber de curvas**: recorres las 100 curvas del volumen a **60 fps** con flechas o
  arrastrando; la curva y el ajuste se actualizan en vivo (pyqtgraph, sin lag).
- **Overlay de ajuste** con **residuos** y **banda de confianza 95%** (de la
  incertidumbre Monte Carlo del core). Ver el residuo es ver si el modelo miente.
- **Segmentos** approach (teal) / retract (ámbar) con el punto de contacto marcado y los
  eventos (ruptura) si los hay.
- **Inspector** contextual: módulo ± σ, R², adhesión, disipación, modelo, y un
  desplegable **provenance** con la receta exacta + hash de fuente (exportable RO-Crate).

---

## 6. Perspectiva "Force-volume / Mapa" (brushing ligado)

```
┌───────────────────────────────┬───────────────────────────────────────────────┐
│         MAPA DE MÓDULO         │              CURVA DEL PÍXEL                   │
│   ▓▒░▒▓▓▒░ (batlow)  10×10     │   (la curva bajo el cursor del mapa, en vivo)  │
│   ░▒▓█▓▒░▒                     │   fuerza ╱fit                                 │
│   ▒▓█[·]█▒   ← cursor          │        ╱                                       │
│   ▓▒░▒▓▒░▒                     │   ────╱────────▶ sep                           │
├───────────────────────────────┼───────────────────────────────────────────────┤
│  HISTOGRAMA (E)                │  ESTADÍSTICA                                   │
│  ▁▂▅█▇▃▁   [brush 2–5 kPa]     │  n=97/100 · mediana 4.6 kPa · σ 1.2 · IQR …    │
│  ▲ al pintar un rango, se      │  [mapa: E | adhesión | disipación | R² | h0]  │
│    resaltan los píxeles ▲      │  [▶ Correr en paralelo]  [⤓ CSV] [⤓ PNG] [RO] │
└───────────────────────────────┴───────────────────────────────────────────────┘
```

- **Linked brushing bidireccional**: pasas el cursor por un píxel → su curva aparece;
  pintas un rango en el histograma → se resaltan los píxeles correspondientes en el mapa.
  Esto convierte un mapa en una herramienta de *exploración*, no una postal.
- Selector de propiedad (E / adhesión / disipación / R² / altura de contacto).
- **Correr en paralelo** usa el `ProcessPoolExecutor` del core con barra de progreso
  cancelable — nunca congela.
- Exportar mapa (PNG con colorbar), CSV, o **paquete RO-Crate** (datos + receta + hash).

---

## 7. Paleta de comandos y teclado

`Cmd/Ctrl-K` abre la **paleta de comandos** con búsqueda difusa de TODO: acciones,
archivos, canales, curvas, perspectivas, ajustes, recetas.

```
┌ ⌘K ─────────────────────────────────────────────────────────┐
│  › ajust                                                     │
│    Ajustar elasticidad (Hertz)                    ⏎          │
│    Ajustar todo el mapa                           ⇧⏎         │
│    Cambiar modelo → DMT                                      │
│    Ajuste: Monte Carlo (incertidumbre)                      │
└──────────────────────────────────────────────────────────────┘
```

Esquema de atajos (configurable, ver §9):

| Acción | Atajo |
|---|---|
| Paleta de comandos | `⌘K` / `Ctrl+K` |
| Abrir archivo / carpeta | `⌘O` / `⌘⇧O` |
| Perspectivas 1–6 | `⌘1 … ⌘6` |
| Curva anterior / siguiente | `←` / `→` (o `,` `.`) |
| Ajustar / ajustar todo | `F` / `⇧F` |
| Correr pipeline | `⌘⏎` |
| Grabar receta | `⌘R` |
| Deshacer / rehacer | `⌘Z` / `⌘⇧Z` |
| Guardar proyecto | `⌘S` |
| Exportar figura | `⌘E` |
| Tema claro/oscuro | `⌘⇧L` |
| Modo foco (zen) | `⌘.` |
| Densidad compacta | `Ctrl+Shift+D` |

---

## 8. Arquitectura técnica (PyQt6)

Nueva estructura de `gui/`, reemplazando las 7 pestañas. **El core sigue puro**; la GUI
solo orquesta y presenta.

```
gui/
├── app.py                      # entrypoint (se conserva, adelgazado)
├── shell/
│   ├── workspace.py            # ventana + dock manager + barra de perspectivas
│   ├── dock_manager.py         # registro/persistencia de paneles y layouts
│   ├── command_palette.py      # ⌘K, índice difuso de comandos
│   ├── status_bar.py           # estado + progreso cancelable global
│   └── perspectives.py         # presets de layout por tarea
├── design/
│   ├── tokens.py               # tokens de color/tipografía/espacio (fuente única)
│   ├── theme.py                # tokens → QSS + pyqtgraph + matplotlib (motor de tema)
│   └── icons.py                # set de iconos SVG
├── panels/                     # cada panel es autocontenido y registrable
│   ├── base.py                 # Panel base (título, toolbar, estado, error, refresh)
│   ├── navigator.py            # árbol archivos/curvas/canales + thumbnail de mapa
│   ├── inspector.py            # propiedades contextuales del objeto activo
│   ├── image_canvas.py         # heatmap pyqtgraph (perspectiva Imagen)
│   ├── force_canvas.py         # curva de fuerza + overlay de ajuste + scrubber
│   ├── map_canvas.py           # force-volume + brushing ligado
│   ├── pipeline_panel.py       # el Recipe visual editable/grabable
│   ├── results_console.py      # readouts tabulares + histogramas + stats
│   ├── figure_editor.py        # editor de figura de publicación (migra el actual)
│   ├── simulator.py            # gemelo digital / enseñanza (migra el actual)
│   └── log_panel.py            # log estructurado (reproducibilidad/debug)
├── viewmodels/                 # estado observable por perspectiva/panel (sin lógica de física)
│   ├── force_vm.py             # curva/volumen activos, receta, resultados
│   └── image_vm.py
├── runtime/
│   ├── tasks.py                # QThreadPool + Runnable + señal de progreso/cancel
│   ├── session.py              # proyecto .spmproj (guardar/restaurar todo)
│   └── settings.py             # QSettings + esquema de preferencias
└── plugins.py                  # descubrimiento de paneles/ops por entry-points
```

### 8.1 Modelo de presentación (sin fugas al core)

Vista (panel) ↔ **ViewModel** (estado observable, señales Qt) ↔ **core** (funciones
puras). El panel nunca importa parsers ni implementa física; solo llama la API pública
del core y refleja el ViewModel. Los ViewModels emiten `pyqtSignal` cuando cambian; los
paneles se re-renderizan reactivamente. Esto elimina la duplicación actual entre tabs.

```python
class ForceViewModel(QObject):
    curveChanged = pyqtSignal()
    resultsChanged = pyqtSignal(dict)      # ctx del pipeline
    recipeChanged = pyqtSignal(Recipe)

    def set_curve(self, index): ...        # cambia curva activa → curveChanged
    def run_pipeline(self): ...            # corre en un Task → resultsChanged
```

### 8.2 Threading — nunca congelar

Contrato: **nada pesado en el hilo de UI**. Todo `fit_all`, mapa, reporte, carga o GIF
va a un `Task` (QRunnable en un QThreadPool). El **callback de progreso del core**
(`progress(fracción, msg)`) se conecta a un `pyqtSignal` que actualiza la barra de estado
y permite **Cancelar**.

```python
class Task(QRunnable):
    def __init__(self, fn, *args, on_progress, on_done, on_error): ...
    def run(self):
        try:
            result = self._fn(*self._args, progress=self._emit_progress)
            self.signals.done.emit(result)
        except Exception as exc:
            self.signals.error.emit(exc)     # → toast + log, nunca swallow silencioso
```

Para mapas de force-volume, el core ya paraleliza con `ProcessPoolExecutor`; la GUI lo
lanza dentro de un `Task` y el callback de progreso llega desde el proceso principal a
medida que llegan resultados (as_completed). Cancelar detiene el pool.

### 8.3 Motor de tema (un token, tres destinos)

`design/theme.py` toma los tokens y genera: (a) el **QSS** de Qt (plantilla con
sustitución), (b) el tema de **pyqtgraph** (`setConfigOption` background/foreground +
pens/colormaps), y (c) el **estilo de matplotlib** (rcParams: face/edge/tick/grid/font).
Cambiar de claro/oscuro es **hot-swap**: re-aplica QSS y re-pinta canvases. Esto arregla
el bug actual de que los plots no siguen el tema.

### 8.4 Estado y persistencia (`.spmproj`)

Un proyecto es un JSON que guarda: archivos cargados (rutas + hash), la receta, los
parámetros por panel, el **layout de docks**, las anotaciones de figura, y la perspectiva
activa. Reabrir un `.spmproj` deja el análisis **exactamente** donde estaba. `QSettings`
guarda preferencias globales (tema, densidad, atajos, layouts con nombre).

### 8.5 Paneles como plugins (entry-points)

Descubrimiento vía `importlib.metadata` sobre el grupo `spmkit.gui_panels`: un lab hace
`pip install spmkit-mi-panel` y aparece en el menú "Añadir panel" sin forkear. El mismo
mecanismo (`spmkit.analyses`) registra **ops de pipeline** custom. La UI es expandible por
la comunidad, no solo por nosotros.

### 8.6 Testing de GUI

`pytest-qt` con `QT_QPA_PLATFORM=offscreen` en CI (hoy los tests de GUI ni corren).
Smoke tests: cada panel monta sin datos; carga de archivo sintético; el pipeline corre y
emite señales; snapshots de layout. Threading testeado con señales esperadas (no sleeps).

---

## 9. Configurabilidad y extensibilidad (nivel VS Code / Blender)

1. **Layouts guardables**: arrastra paneles a donde quieras, guarda "layouts con nombre".
   Presets de fábrica: *Nanomecánica*, *Force-volume*, *Enseñanza*, *Póster/Revista*.
2. **Preferencias por esquema**: un panel de Ajustes generado desde un esquema
   (tipos + defaults + descripciones). Precedencia: **defaults < usuario (`QSettings`) <
   proyecto (`.spmproj`)**. Todo descubrible y buscable desde `⌘K`.
3. **Editor de tema en vivo**: edita tokens y ve el cambio al instante; crea colormaps,
   importa Crameri. Exporta/importa temas como archivo.
4. **Editor de atajos**: reasigna cualquier atajo; detecta colisiones; export/import.
5. **UI dirigida por recetas**: el pipeline de análisis es YAML del usuario —
   compartible, versionable, revisable en Git. Las recetas de `examples/recipes/` son
   plantillas de arranque.
6. **Plugins**: paneles y ops de análisis por entry-points (§8.5).
7. **Plantillas de figura/reporte**: presets de revista/póster (tamaño, DPI, tipografía,
   colormap) aplicables con un clic.
8. **i18n (ES/EN)**: strings de UI externalizados; identificadores/código en español
   (elección UTFSM), interfaz conmutable a inglés para audiencia internacional.

---

## 10. Features de firma (el factor wow)

| Feature | Qué es | Por qué encanta | Cómo se construye |
|---|---|---|---|
| **Scrubbing 60fps** | Recorrer 10.000 curvas en vivo | Se siente instantáneo, como un osciloscopio | pyqtgraph `setData` + lazy loader del core + coalesce con QTimer |
| **Brushing ligado** | mapa↔curva↔histograma vinculados | Convierte un mapa en exploración | Selecciones compartidas en el ViewModel + señales |
| **Pipeline vivo** | Editar un paso re-ejecuta y previsualiza | La ciencia se vuelve tangible | Recipe del core + Task sobre la curva visible |
| **Overlay de ajuste** | Fit + residuos + banda 95% | Ver si el modelo miente | Monte Carlo del core → `FillBetweenItem` |
| **Paleta de comandos** | ⌘K difuso a todo | Cero búsqueda en menús | índice de comandos + rapidfuzz |
| **Modo foco (zen)** | Oculta docks, solo el dato | Concentración total | toggle de docks + fade |
| **Modo enseñanza** | Gemelo digital: cambias k/T/R y ves el ruido térmico y Hertz responder | Un profe lo demuestra y lo recuerda | `simulation.py` del core + sliders + curva viva |
| **Superficie de provenance** | Cada resultado muestra su receta + hash; exporta RO-Crate | Reproducibilidad FAIR, único frente a ANA/JPK | receta del core + `trace_nid` + empaquetado |
| **Primer arranque hermoso** | Pantalla de bienvenida con drag&drop, recientes, y una demo de 1 clic | La primera impresión vende | welcome panel + dataset demo empacado |
| **Movimiento con gusto** | Skeletons al cargar, transición spring entre perspectivas | Se siente moderno sin distraer | animaciones QSS/`QPropertyAnimation` ≤260ms |

---

## 11. Migración desde las 7 pestañas (sin romper la app)

Estrategia de bajo riesgo, incremental, siempre con la app funcionando:

- **Fase A — Cimientos** ✅: `design/tokens.py` + motor de tema (QSS/pyqtgraph/matplotlib
  sincronizados) + `runtime/tasks.py` (threading) + `panels/base.py`.
- **Fase B — Shell** ✅: `shell/workspace.py` con dock manager + barra de perspectivas +
  paleta de comandos (⌘K) + barra de estado con progreso cancelable.
- **Fase C — Perspectiva Curva de fuerza** ✅: `force_canvas` (datos+ajuste+residuos+
  indentación δ+región manual+fijar curvas) + `pipeline_panel` en vivo (modelo/geometría/
  Poisson/suavizado/calibración) + `inspector` (E±σ, R², adhesión, disipación, F/δ máx).
- **Fase D — Perspectiva Mapa** ✅ (brushing ligado, ImageView, histograma, export) y
  **Batch** ✅ (carpeta→tabla→CSV, paralelo). Lanzable con `spmkit workspace [archivo]`.
- **Fase E — Migrar** Imagen/Figura/Simulador a paneles nativos; retirar las tabs viejas
  (pendiente).
- **Fase F — Extensibilidad**: persistencia (tema/geometría/perspectiva) ✅; pendientes:
  layouts guardables, editor de tema/atajos, plugins, `.spmproj`, i18n. Posible modelo JKR
  (con validación previa; hoy están Hertz/paraboloide/Sneddon/DMT).

Cada fase entró con smoke tests de GUI (pytest-qt offscreen) y dejó la app usable.
Verificado end-to-end con datos reales (JPK y force-volume `.nid` 10×10).

---

## 12. Definición de "listo" (calidad de la obra)

- [ ] DFII ≥ 8 (aquí 15) y el **ancla de diferenciación** visible en pantalla.
- [ ] Cero congelamientos: toda operación pesada con progreso cancelable.
- [ ] Tema claro/oscuro hot-swap con gráficos que **siguen** el tema.
- [ ] Teclado-primero: todo accionable sin mouse; `⌘K` completa.
- [ ] Reproducibilidad visible: cada resultado muestra su receta; `.spmproj` restaura todo.
- [ ] Configurable sin código: layouts, tema, atajos, plugins.
- [ ] Accesible: contraste AA, foco visible, `prefers-reduced-motion`.
- [ ] Se ve como un **instrumento**, no como un template. Si dudas, reinicia.

---

## 13. Refinamientos tras revisión senior (v2)

Ajustes que corrigen puntos ciegos arquitectónicos detectados en revisión. DFII
recalibrado a **14/15** (−1 por el riesgo técnico de scrubbing 60fps + IPC, mitigado
abajo).

### 13.1 Jerarquía de color de trazas (CRÍTICO — corrige *halation*)
Un teal brillante sobre grafito casi negro produce **halation** (halo que difumina el
borde de la curva) y arruina la precisión al localizar el punto de contacto. Regla nueva:
- **Datos crudos = neutral frío.** Extend `#C9D3DE` (blanco desaturado), retract
  `#B49A6E` (ámbar apagado, no saturado). Son el sustrato, no el foco.
- **Teal `#2DD4BF` RESERVADO** al **ajuste (fit)**, la **traza activa/seleccionada** y el
  marcador de **contacto**. El modelo es el héroe visual, no el ruido.
- Jerarquía inmediata: **gris = dato/ruido, teal = modelo/ajuste**. (Actualiza §2.1 y §5.)

### 13.2 Peso 600 en modo claro (legibilidad AA)
En modo claro, texto 400 sobre papel cálido puede sentirse "lavado". Se permite **peso
600 solo para labels de sección y headers críticos** en modo claro; el resto sigue 400/500
(en oscuro nunca >500, para evitar halo). El peso no cambia el contraste (eso es color),
pero sí la legibilidad a tamaños chicos.

### 13.3 Scrubbing sin recomputar (rendimiento real)
El cuello de botella del scrubbing no es el render (pyqtgraph es C++/GPU) sino el **I/O y
el recálculo del pipeline**. Solución:
- Al **hacer scrub, solo se re-renderiza la curva** (lazy loader del core + caché **LRU**
  de curvas en el ViewModel); NO se corre el pipeline.
- El **ajuste corre con debounce** (`QTimer.singleShot(150ms)`) tras soltar el cursor.
- Los resultados por curva se **precalculan en background** (Task) y se cachean; al pasar
  por una curva ya calculada, el overlay aparece instantáneo.

### 13.4 Optimistic UI en el pipeline (estados transitorios)
Editar un paso en vivo puede dejar el pipeline momentáneamente inválido. Regla: si un paso
falla al evaluar, se marca con **warning naranja** en ese paso, **se conserva en pantalla
el último resultado válido** y el scrubbing **no se rompe**. El usuario sigue trabajando;
el error es reversible y localizado.

### 13.5 Sandbox de paneles/plugins (aislamiento de fallos)
Un plugin de terceros que crashea **no puede tumbar la app**. El `Panel base` envuelve el
render en un try/except: ante una excepción muestra un **"Error Card"** dentro del panel
(mensaje + traceback plegable + `[Reiniciar panel]` `[Reportar]`), como VS Code con
extensiones rotas. El resto del workspace sigue vivo.

### 13.6 IPC seguro pool↔Qt (CRÍTICO — nunca emitir desde un hijo)
Fronteras explícitas para no crashear Qt:
- Los **procesos hijo** del `ProcessPoolExecutor` son **cómputo puro**: jamás importan ni
  tocan Qt ni emiten señales.
- El pool corre dentro del **hilo worker** del `QThreadPool` (mismo proceso que la UI, pero
  no el hilo principal). El callback de progreso se ejecuta ahí y **emite un `pyqtSignal`**,
  que Qt **encola de forma segura** al hilo principal (conexión cross-thread por defecto).
- Alternativa aún más desacoplada (recomendada si el pool se vuelve complejo):
  `multiprocessing.Queue` para el progreso + un `QTimer` en la UI que hace **polling cada
  50ms** y emite la señal. Cero acoplamiento entre el pool y Qt.

### 13.7 `.spmproj` versionado y tolerante
El JSON del proyecto lleva `schema_version` estricto y funciones `migrate_vN_a_vN1()`. Si
al abrir un proyecto un panel del layout **no existe** (plugin desinstalado, panel
renombrado), la app lo **ignora con gracia** y abre el resto — nunca falla la apertura.

### 13.8 Abstracción de `Canvas` (a prueba de futuro)
Todos los objetos de pyqtgraph se envuelven en una clase propia `Canvas`
(`draw_curve/draw_map/set_theme/...`). Los paneles hablan con `Canvas`, no con pyqtgraph
directo. Así, si mañana migramos a **vispy/pygfx** (GPU puro) por rendimiento, se cambia
`Canvas` sin reescribir un solo panel.

### 13.9 Orden de ejecución y spikes
- **Empezar por Fase A** (tokens + threading). Si no se paraleliza un mapa 100×100 sin
  congelar la UI, lo demás no importa.
- **Spike de brushing (2 días)** antes de la Fase D: prototipo mínimo en pyqtgraph que
  sincronice un heatmap y un histograma (selección bidireccional). Es lo más difícil de
  sincronizar; validarlo temprano de-riesga la killer feature.

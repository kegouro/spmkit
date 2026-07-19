# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y
el versionado es [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Changed
- Sincronizada la metadata de desarrollo en `0.1.5.dev0`; la cita conserva la última release publicada.

### Validación — hito Nanoscope SPM v0.1
- Soporte nativo limitado para imágenes Nanoscope III `.spm`, documentado con seis
  archivos demostrados frente a Gwyddion 2.71. El alcance permanece **parcial** y
  `LEVEL 2 NUMERICALLY_VERIFIED`; la confirmación externa prerregistrada no es un
  blind holdout por `ACCIDENTAL_PRE_FREEZE_UNBLINDING`.

### Documentación — Guía de extensión y guía de usuario Fathom (F5 del roadmap)
- **Nueva guía "Extender spmkit y Fathom"** (`docs/extending.md`): los tres puntos de
  extensión (formatos/análisis por `spmkit.plugins.v1`, perspectivas/paneles por `ModuleSpec`
  + entry-point `spmkit.gui.modules`, dominios de otro core) con ejemplos y checklist.
- **Guía de usuario reescrita a Fathom**: perspectivas (imagen/granos/espectral/curva/mapa/
  batch/figura/3D/simulador), apertura por capacidades, personalización de apariencia,
  proyectos `.spmproj`, informes/export y atajos. Sustituye la guía de la app clásica (que
  sigue disponible con `spmkit gui --legacy`).

### Añadido — Personalización de apariencia (F4 del roadmap)
- **Diálogo de apariencia** (⌘⇧A o paleta → "Personalizar apariencia…"): elige **tema**,
  **acento** y **tamaño de fuente** con **vista previa en vivo** (cancelar revierte) y
  persistencia entre sesiones. Los temas se muestran como **tarjetas** pintadas con sus
  propios colores.
- **Presets de tema** listos: Grafito (oscuro), Papel (claro), **NanoSurf oro** (marca),
  **Nord**, **Dracula**, **Solarized** (oscuro/claro) y **Gruvbox**. Cada preset alimenta a
  la vez QSS, pyqtgraph y matplotlib (los gráficos siguen el tema).
- **Acento personalizado**: cualquier color; deriva solo sus variantes (pulsado/suave/texto
  legible). **Escala tipográfica** (Compacto/Normal/Cómodo/Grande). El atajo ⌘⇧L sigue
  alternando claro/oscuro rápido preservando acento y fuente.

### Cambiado — Estructura de módulos/extensiones de Fathom (F4 del roadmap)
- **Añadir un módulo es un trámite tonto**: la app se **ensambla desde módulos**
  (`gui/extensions.py`, `gui/builtin_modules.py`). Un `ModuleSpec` declara sus **paneles**
  (con *factory* perezosa sobre un `ModuleContext` con los hubs compartidos) y sus
  **perspectivas**; `build_workspace` deriva de ahí la barra de perspectivas, los docks, los
  lienzos y el cableado. **Sumar una perspectiva = añadir un `ModuleSpec`** — cero cambios en
  la shell (antes tocaba 5-7 sitios).
- **Descubrimiento por entry-points** (grupo `spmkit.gui.modules`): un tercero u **otro core
  multi-física** publica sus módulos sin tocar `spmkit`. Prepara a `spmkit` como *host* y a
  Fathom como una de sus extensiones (AFM/fuerza). Un plugin roto se ignora sin tumbar la app;
  ante choque de claves gana el módulo de fábrica.
- La shell (`Workspace`) es agnóstica del catálogo: recibe perspectivas/paneles/áreas
  inyectados (defaults derivados de los módulos de fábrica). Sin regresión funcional.

### Añadido — Modelos mecánicos experimentales, *flagged* (F3.3 del roadmap)
- **JKR** (contacto adhesivo Johnson-Kendall-Roberts) y **viscoelástico SLS**
  (relajación de fuerza) en `core.analysis.experimental`, ajuste numpy puro (búsqueda en
  grilla). ⚠️ **Experimentales / sin validar** contra referencia independiente: se
  incluyen marcados (`EXPERIMENTAL = True`, `experimental=True` en los resultados) para
  revalidarlos en el futuro; **no** usar para publicar. Verificados sólo contra límites
  analíticos (JKR→Hertz con adhesión nula; relajación con τ conocido).
- **CLI `spmkit jkr`** (con banner de advertencia) ajusta JKR a una curva calibrada,
  reutilizando la extracción de contacto **validada** (`forcecurve.contact_indentation`,
  refactor sin cambio de comportamiento del ajuste Hertz/DMT).

### Añadido — Análisis de imagen completo en Fathom (F3 del roadmap)
- **Paridad de visor** en la perspectiva Imagen: selector de colormap, nivelado
  plano/polinomio/**por filas**, y **perfil de línea interactivo** (ROI arrastrable) con
  gráfico y exportación a CSV; lectura de rugosidad (Sa/Sq/Sz/Ssk/Sku) y **KPFM/CPD**
  para canales de potencial (`ImageAnalysisPanel`).
- **Detección de granos** (perspectiva Granos, paridad JPK/ANA): segmenta partículas
  sobre la topografía nivelada con overlay coloreado y estadística (conteo, diámetro
  equivalente medio, cobertura, densidad por µm²). Parámetros ajustables (tamaño mínimo,
  altura relativa). Requiere scipy (extra `grains`); avisa si falta, sin tumbar la app.
- **Análisis espectral** (perspectiva Espectral): PSD radialmente promediada en log-log
  + exponente de Hurst / **dimensión fractal** + longitud de correlación. Antes solo en
  la CLI; ahora en la GUI. Todo reutiliza el `core.analysis` puro sobre el hub de imagen.

### Añadido — Plataforma de formatos y plugins (F1 del roadmap)
- **Sistema de plugins versionado** (`core/plugins/`, `spmkit.plugins.v1`): contratos
  ``Reader``/``DatasetInfo``/``Analysis``/``Domain`` como ``Protocol``s estables +
  registry con descubrimiento por entry-points. Prepara a `spmkit` como **host
  multi-física** y a Fathom como su extensión de AFM.
- **Dispatch por capacidades** (`core/io/loadany.py`): ``inspect_any`` (barato, solo
  cabecera) declara qué contiene un archivo; ``load_any(path, kind)`` carga el tipo
  pedido. Un `.nid`/QI que trae imagen **y** curvas ofrece elegir cómo abrirlo.
- **Lector opcional `afmformats`** (extra `afm`): JPK QI/force-map, Asylum `.ibw`, HDF5,
  NT-MDT, `.tab`, validado contra samples open-source reales (Asylum SiN → 30.8 MPa).
- **Arnés de datos de prueba** (`scripts/fetch_samples.py`): descarga samples
  open-source por formato a `reference/` (gitignored); tests con `skipif`.
- **Test de arquitectura** (`tests/test_architecture.py`): hace **cumplir como código**
  que `core/` no importe UI (atrapó y corrigió un acoplamiento real con pyqtgraph).
- GUI (Fathom) y CLI de fuerza abren cualquier formato registrado vía `load_any`.

### Añadido — Plataforma de espectroscopía de fuerza (curvas de fuerza)
- **Modelo de datos de curvas de fuerza** (`core/models/force.py`): `ForceSegment`
  (extend/retract/pause con canales crudos + estado de calibración), `ForceCurve`
  y `ForceVolume` con **carga perezosa** (loader picklable) para mapas grandes.
- **Motor de pipeline reproducible** (`core/pipeline/`): `Recipe` serializable a
  YAML (la GUI podrá grabarlo), condiciones seguras evaluadas con `ast` (sin
  `eval()`), registro de operaciones y ejecución con callback de progreso.
- **Calibración del cantiléver** (`core/analysis/calibration.py`): sensibilidad de
  deflexión (InVOLS), constante de resorte por ruido térmico (Butt-Jaschke).
- **Mecánica nativa de curvas de fuerza** (`core/analysis/forcecurve.py`): ajuste
  robusto al signo/orden del eje (JPK y NanoSurf a la par), modelos Hertz/
  paraboloide/cono/DMT, incertidumbre **Monte Carlo** (propaga InVOLS y k),
  adhesión y **energía de disipación** (histéresis approach/retract).
- **Lectores de curvas de fuerza**: `.jpk-force` (JPK/Bruker, con calibración
  desde metadatos) y force-volume `.nid` (NanoSurf, extend/retract).
- **Mapas de force-volume** (`core/analysis/forcevolume.py`): corre el pipeline
  por píxel → mapas de módulo/adhesión/disipación + estadística e histogramas,
  con **ejecución en paralelo** opcional.
- **Batch de curvas de fuerza** (`core/forcebatch.py`): procesa una carpeta de
  archivos → tabla resumen (`to_csv`/`to_dataframe`).
- **CLI**: comandos `forcecurve`, `forcemap` y `fbatch`.

### Añadido — Fathom: workspace de curvas de fuerza (rediseño de UI)
- **Fathom**, el workspace de curvas de fuerza (producto sobre la librería `spmkit`),
  pensado para **reemplazar Nanosurf ANA y JPK Data Processing**. Se lanza con
  `spmkit workspace [archivo]`. Estética "Instrumento": grafito + teal + oro; MVVM;
  perspectivas + paleta de comandos (⌘K) en vez de pestañas planas.
- **Perspectiva Curva de fuerza**: lienzo con approach/retract, overlay de ajuste,
  **tira de residuos**, eje conmuta separación/**indentación δ**, **región de ajuste
  manual**, **fijar/superponer curvas**; **pipeline en vivo** (modelo Hertz/paraboloide/
  Sneddon/DMT, radio, Poisson, semiángulo, **suavizado Savitzky-Golay**, calibración);
  inspector con E±σ, R², adhesión, disipación, F máx y δ máx.
- **Perspectiva Mapa** (force-volume): imagen de propiedad + **linked brushing** +
  histograma; **motor de cálculo CPU/GPU** con ruta **vectorizada** (misma física a
  precisión de máquina, mucho más rápida; GPU vía CuPy/CUDA) y pop-up explicativo.
- **Perspectiva Batch**: carpeta → tabla → CSV (paralelo). **Perspectiva Imagen**:
  visor de canal + nivelado + rugosidad (colormap gold).
- **Optimización**: `core/compute.py` (backend CPU/GPU) y `core/analysis/forcevolume_fast.py`
  (mapa de elasticidad vectorizado, validado contra el ajuste por curva). `forcemap`
  gana `--fast/--pipeline` y `--backend cpu|gpu`.
- **Informe magistral** (`core/forcereport.py`): informe profesional de un force-volume
  en **HTML** (autocontenido), **LaTeX** (`.tex`) y **PDF** (compilado con tectonic/
  pdflatex) — con tabla de estadística, mapas de propiedades, histogramas y una curva
  representativa. CLI `spmkit forcereport`; comando "Generar informe" en Fathom.
- **Exportar todo** (`core/forceexport.py`): vuelca a una carpeta los mapas en CSV, una
  tabla por curva, el resumen estadístico y el informe. CLI `spmkit forceexport`; comando
  "Exportar todo" en Fathom.
- **Calidad de vida**: exportar figura/mapa/JSON, copiar resultados, navegación por
  teclado, **arrastrar y soltar** archivos, temas claro/oscuro con **persistencia**
  (tema/geometría/perspectiva), panel de log, memoria del último directorio.

### Mejorado — app clásica (`spmkit gui`)
- **Anotaciones de figura totalmente personalizables** (editor de figuras): color,
  tamaño, negrita/cursiva, fuente, alineación de ancla, **justificado** multilínea,
  **interlineado**, rotación y **fondo** (color sólido o **semitransparente con selector
  de opacidad** y borde opcional). Se editan con doble-clic y se arrastran.
- **Vista 3D**: el eje Z se muestra en **unidades físicas legibles** (nm/µm) en vez de
  metros crudos con `1e-6`; la exageración pasó a ser un **estiramiento visual** (los
  valores del eje son alturas reales, honestas).
- **Acceso a Fathom** desde la barra de la app clásica (curvas de fuerza, mapas y batch).

### Añadido — Fathom: unificación y perspectivas migradas (F2 del roadmap)
- **Fathom es el default** (`spmkit gui`); la app clásica se conserva intacta y
  documentada como legacy (`spmkit gui --legacy`), sin perder su historia (`git mv`).
- **Proyecto `.spmproj`** (`core/project.py`, puro/versionado/tolerante): guarda archivo
  abierto + receta + perspectiva; comandos Guardar/Abrir proyecto en Fathom.
- **Figura, Vista 3D y Simulador migrados a perspectivas MVVM** (ViewModel + panel):
  el editor de figuras (spec + anotaciones ricas arrastrables), la superficie 3D
  (exageración Z visual, hillshade, Z en nm/µm) y el gemelo digital del cantiléver
  comparten el **hub de imagen** y reutilizan el `core.viz`/`core.analysis` puro. Dejan
  de ser placeholders. El diálogo de anotaciones vive en `gui/widgets/` (fuente única
  compartida con la app clásica). La shell refresca el panel central al activar su
  perspectiva (corrige el lienzo en blanco del simulador).

### Añadido
- **Nanomecánica — modelo DMT** (Derjaguin-Muller-Toporov): Hertz esférico con la
  adhesión como offset constante, para muestras rígidas con adhesión no
  despreciable (`--model dmt`).
- **Incertidumbre y bondad de ajuste**: `IndentationResult` ahora reporta la
  incertidumbre 1σ del módulo (`young_modulus_std`), el `r_squared` y el número
  de puntos ajustados (`n_fit`); la CLI `nanomech` los muestra (`E ± σ`, `R²`).
- **Detección de contacto robusta** por *ratio of variances* (Gavara 2016),
  seleccionable con `--contact-method rov` (más robusto al ruido que el umbral
  de k·σ).
- Factor de corrección de forma de modo (`correction_factor`, Butt-Jaschke) en
  `thermal_spring_constant` para calibración por palanca óptica.
- Tests known-answer para los modelos DMT y cónico (Sneddon), momentos
  gaussianos de rugosidad (Ssk≈0, Sku≈3) y contacto bajo ruido.

### Corregido
- `adhesion` en el ajuste de curvas se mide ahora sobre la curva **corregida de
  línea base** (antes usaba la curva cruda, sesgando el pull-off por el offset).
- `fit_all` propaga el semiángulo (`half_angle`) a cada ajuste cónico (antes
  quedaba fijo en 20° en los mapas de módulo).
- CLI `nanomech`: valida el índice de curva fuera de rango con un mensaje claro
  en vez de un `IndexError`.
- Docstring de `thermal_spring_constant` con un ejemplo numérico incorrecto
  (×100); corregido y verificado.
- **Privacidad**: se retiraron de la documentación pública (`VALIDATION.md`,
  `cli.md`) el identificador de muestra del lab y un valor medido específico,
  según la política de neutralidad experimental del proyecto.

## [0.1.2] - 2026-06-16

### Cambiado
- Documentación y textos de la interfaz generalizados (la teoría se presenta de
  forma general, sin contexto experimental específico).

### Corregido
- Simulador (gemelo digital): se corrige el lienzo en negro en pantallas HiDPI
  (render diferido al mostrarse, dibujo síncrono y fondo blanco explícito).
- Visor: la imagen se ajusta automáticamente al panel al abrir un archivo.

## [0.1.1] - 2026-06-16

### Añadido
- **Sensado de masa por posición de carga**: constante de resorte efectiva k(x)=k(L)/(x/L)³ según la posición de carga x/L de la masa; fórmula Δm = k(x)/(4π²)·(1/f₁²−1/f₀²), con control de posición en la GUI y opción --position en la CLI.
- **Evaporación avanzada**: ajuste SHO/Lorentziano del pico, ley d² (radio de
  gota, régimen de difusión) y exportación de la evaporación como animación GIF.
- **Vista 3D** de topografía (superficie con dorado, hillshade, exageración Z).
- **Análisis espectral**: PSD radial, exponente de Hurst, dimensión fractal y
  longitud de correlación (`spmkit psd`).
- **Gemelo digital** del cantiléver (pestaña Simulador): espectro de ruido
  térmico y corrimiento de resonancia por masa añadida, normalizado por
  equipartición.
- **Resonancia y sensado de masa** (`core/analysis/resonance.py`): lee espectros
  de *thermal tuning* de NanoSurf, detecta la resonancia y sigue la masa por
  desplazamiento de frecuencia (`m = k/(2πf)²`, `Δf ∝ Δm`). Pestaña GUI
  **Resonancia** y comando `spmkit evaporation` para seguimiento de masa en el
  tiempo: f(t), masa añadida Δm(t) y tasa dΔm/dt.
- **Detección de granos/partículas** (`core/analysis/grains.py`, extra `[grains]`):
  segmentación con `scipy.ndimage`, estadística de tamaños (diámetro equivalente,
  cobertura, densidad) y comando `spmkit grains`.
- **Calibración de constante de resorte** del cantiléver: método de equipartición
  (`mechanics.thermal_spring_constant`) y `spring_constant` en CLI (`--spring-constant`)
  y GUI para corregir la indentación en el ajuste mecánico.

## [0.1.0] - 2026-06-15

### Añadido
- Lectura de NanoSurf `.nid` (validada contra Gwyddion) y `.nhf`; interop
  Gwyddion `.gwy` (lectura/escritura vía `gwyfile`).
- Análisis: rugosidad ISO 25178, nivelación, perfiles de línea, KPFM (CPD /
  función de trabajo) y nanomecánica (Hertz/Sneddon, mapas de módulo/adhesión).
- Visualización: figuras de publicación con colormaps científicos (incluido el
  dorado estilo NanoSurf), barra de escala, editor WYSIWYG con textos
  arrastrables y rango de color `vmin/vmax`.
- Comparación multi-archivo (2–4) con colorbar y escala compartidas.
- Reportes HTML, procesamiento por lotes, exportación CSV/JSON/HDF5/PNG/SVG/PDF.
- GUI por pestañas (Visor · Nanomecánica · Editor · Comparar) con tema
  claro/oscuro persistente, atajos de teclado, recientes, drag & drop y
  diálogo de bienvenida.
- CLI `spmkit` (info, roughness, analyze, nanomech, batch, figure, convert, gui).

### Validado
- Lectura del `.nid` exacta a precisión de máquina contra el export `.gwy` del
  lab; orientación de imagen consistente con Gwyddion/NanoSurf.

[Unreleased]: https://github.com/kegouro/spmkit/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/kegouro/spmkit/releases/tag/v0.1.2
[0.1.1]: https://github.com/kegouro/spmkit/releases/tag/v0.1.1
[0.1.0]: https://github.com/kegouro/spmkit/releases/tag/v0.1.0

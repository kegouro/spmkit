# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y
el versionado es [SemVer](https://semver.org/lang/es/).

## [Unreleased]

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

# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y
el versionado es [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Añadido
- **Resonancia y sensado de masa** (`core/analysis/resonance.py`): lee espectros
  de *thermal tuning* de NanoSurf, detecta la resonancia y sigue la masa por
  desplazamiento de frecuencia (`m = k/(2πf)²`, `Δf ∝ Δm`). Pestaña GUI
  **Resonancia** y comando `spmkit evaporation` para evaporación de *liquid
  marbles*: f(t), masa añadida Δm(t) y tasa de evaporación dΔm/dt. Validado con
  datos reales (Δm ≈ 0.85 ng).
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

[Unreleased]: https://github.com/kegouro/spmkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kegouro/spmkit/releases/tag/v0.1.0

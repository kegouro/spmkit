# Roadmap y estado de funcionalidades

## ✅ Implementado

### Análisis
- Rugosidad areal ISO 25178 (Sa, Sq, Sz, Sp, Sv, Ssk, Sku).
- Nivelación: plano, polinómica, alineado de filas.
- Perfiles de línea con interpolación bilineal.
- KPFM: estadísticas de CPD y función de trabajo.
- **Nanomecánica**: extracción de curvas fuerza-distancia, corrección de base,
  detección de punto de contacto, ajuste Hertz (esfera/paraboloide) y Sneddon
  (cono) → módulo de Young, adhesión.

### Formatos e interop
- Lectura `.nid` (validada con archivos del lab), `.nhf` (HDF5), `.gwy`.
- Escritura `.gwy` (round-trip con Gwyddion) + "Abrir en Gwyddion".
- Exportación CSV / JSON / HDF5 / PNG / SVG / PDF.

### Quality of life
- Procesamiento por lotes (carpeta → CSV resumen), CLI `batch`.
- Reportes HTML autocontenidos (imprimibles a PDF).
- Figuras de publicación: colormaps científicos (Crameri), barra de escala.
- Editor de figuras WYSIWYG: edición de título, ejes, colormap, tamaño de
  título, colorbar/scale bar, y **anotaciones de texto arrastrables**.
- GUI por pestañas (Visor · Nanomecánica · Editor de figuras).
- Tema claro/oscuro con toggle, archivos recientes, drag & drop.

## 🚧 Próximos pasos (priorizables)

### Editor de figuras (completar WYSIWYG)
- [ ] Arrastrar/editar título, ejes y colorbar in-situ (hoy: anotaciones).
- [ ] Selector de tipografía y color por elemento (panel de propiedades).
- [ ] Editar límites de color (vmin/vmax) con histograma interactivo.
- [ ] Plantillas de estilo guardables (preset de revista/poster).
- [ ] Leyenda configurable para perfiles y curvas múltiples.

### Análisis
- [ ] Mapas de módulo/adhesión a partir de todas las curvas (no solo una).
- [ ] Corrección por constante de resorte del cantiléver (calibración).
- [ ] Detección de partículas/granos y estadística de tamaños.
- [ ] FFT / análisis de PSD de rugosidad.

### Formatos
- [ ] Validar `.nhf` con archivos reales (o delegar en NSFopen).
- [ ] Soporte de más formatos (Bruker, Asylum) vía AFMReader.

### Infra
- [ ] Empaquetado como app de escritorio (PyInstaller).
- [ ] Publicar en PyPI y activar CI con extra `gui` (offscreen).

## Ideas de la comunidad (GitHub) evaluadas

| Proyecto | Uso potencial |
|----------|---------------|
| [NSFopen](https://pypi.org/project/NSFopen/) | Lector `.nid`/`.nhf` validado (fallback) |
| [gwyfile](https://pypi.org/project/gwyfile/) | Interop `.gwy` (adoptado) |
| [cmcrameri](https://github.com/callumrollo/cmcrameri) | Colormaps perceptuales (adoptado) |
| [matplotlib-scalebar](https://pypi.org/project/matplotlib-scalebar/) | Barra de escala (adoptado) |
| [AFMReader](https://github.com/AFM-SPM/AFMReader) | Más formatos AFM a futuro |
| [nanoforce](https://pypi.org/project/nanoforce/) | Referencia de análisis de fuerza |

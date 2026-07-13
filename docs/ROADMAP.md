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
- Lectura `.nid` (validada externamente), `.nhf` experimental (contrato HDF5
  sintético) y `.gwy` (round-trip).
- Escritura `.gwy` (round-trip con Gwyddion) + "Abrir en Gwyddion".
- Exportación CSV / JSON / HDF5 / PNG / SVG / PDF.

### Quality of life
- Procesamiento por lotes (carpeta → CSV resumen), CLI `batch`.
- Reportes HTML autocontenidos (imprimibles a PDF).
- Figuras de publicación: colormaps científicos (Crameri), barra de escala.
- Editor de figuras WYSIWYG: edición de título, ejes, colormap, tamaño de
  título, colorbar/scale bar, **rango de color vmin/vmax**, y **arrastre de
  título, ejes y anotaciones**.
- **Mapas de módulo/adhesión** a partir de todas las curvas (force-volume).
- **Comparación multi-archivo** (2–4): panel fusionado con colorbar y escala
  compartidas (una por panel si los barridos miden distinto).
- **Reporte HTML completo** con toda la estadística + metadatos.
- GUI por pestañas (Visor · Nanomecánica · Editor de figuras · Comparar).
- Estética "panel de instrumento": tema claro/oscuro, monoespaciado tabular.
- Archivos recientes, drag & drop.

## 🚧 Próximos pasos (priorizables)

### Editor de figuras (pulir WYSIWYG)
- [ ] Persistir la posición arrastrada de título/ejes en el FigureSpec.
- [ ] Selector de tipografía y color por elemento (panel de propiedades).
- [ ] Histograma interactivo para fijar vmin/vmax.
- [ ] Plantillas de estilo guardables (preset de revista/poster).

### Análisis
- [ ] Corrección por constante de resorte del cantiléver (calibración).
- [ ] Detección de partículas/granos y estadística de tamaños.
- [ ] FFT / análisis de PSD de rugosidad.

### Formatos
- [ ] Validar `.nhf` con un oráculo externo y evaluar una integración futura con NSFopen.
- [ ] Soporte de más formatos (Bruker, Asylum) vía AFMReader.

### Infra
- [ ] Empaquetado como app de escritorio (PyInstaller).
- [ ] Publicar en PyPI y activar CI con extra `gui` (offscreen).

## Ideas de la comunidad (GitHub) evaluadas

| Proyecto | Uso potencial |
|----------|---------------|
| [NSFopen](https://pypi.org/project/NSFopen/) | Integración futura evaluable para `.nid`/`.nhf` |
| [gwyfile](https://pypi.org/project/gwyfile/) | Interop `.gwy` (adoptado) |
| [cmcrameri](https://github.com/callumrollo/cmcrameri) | Colormaps perceptuales (adoptado) |
| [matplotlib-scalebar](https://pypi.org/project/matplotlib-scalebar/) | Barra de escala (adoptado) |
| [AFMReader](https://github.com/AFM-SPM/AFMReader) | Más formatos AFM a futuro |
| [nanoforce](https://pypi.org/project/nanoforce/) | Referencia de análisis de fuerza |

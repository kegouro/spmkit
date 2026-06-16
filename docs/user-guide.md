# Guía de usuario — Interfaz gráfica (GUI)

La GUI de spmkit es una aplicación de escritorio construida con **PyQt6 + pyqtgraph**, organizada en **7 pestañas** que cubren desde la visualización de imágenes AFM hasta el análisis avanzado de resonancia y simulación.

## Abrir la GUI

```bash
spmkit gui
```

O desde Python:

```python
from spmkit.gui.app import run
run()
```

!!! note "Requisito"
    Instala el extra `gui` antes: `pip install "spmkit[gui]"`

---

## Pestaña 1 — Visor

La pestaña principal de visualización de imágenes AFM/KPFM.

**Qué hace:**

- Carga archivos `.nid`, `.nhf` y `.gwy` (arrastrar y soltar, o menú Abrir).
- Lista todos los canales del archivo (Z-Axis, CPD, Phase, Deflection, etc.) con dirección forward/backward.
- Muestra el **heatmap** del canal seleccionado con colormap configurable.
- Permite elegir la **nivelación**: plano (`plane`), polinómica (`poly`) o sin nivelar (`none`).
- Panel derecho con **estadísticas de rugosidad** en tiempo real (Sa, Sq, Sz, Ssk, Sku) y estadísticas KPFM si el canal está en voltios.
- **Perfil de línea**: arrastra los extremos de la línea sobre la imagen; el gráfico inferior se actualiza en vivo con interpolación bilineal.
- Exporta el perfil o la rugosidad a CSV con un clic.

---

## Pestaña 2 — Nanomecánica

Análisis de curvas fuerza-distancia (force-volume).

**Qué hace:**

- Carga archivos con espectroscopía (canal `Deflection` o similar).
- Muestra la curva fuerza-distancia seleccionada con corrección de baseline.
- Ajuste de modelos de contacto: **Hertz** (esfera / paraboloide) y **Sneddon** (cono).
- Reporta módulo de Young (MPa / GPa), punto de contacto y adhesión (nN) con RMSE del ajuste.
- Genera **mapas de módulo y adhesión** a partir de todos los puntos del force-volume.
- Admite constante de resorte del cantiléver para corrección de indentación real.

---

## Pestaña 3 — Vista 3D

Visualización tridimensional interactiva de la superficie.

**Qué hace:**

- Renderiza el canal de topografía como una **superficie 3D** usando OpenGL acelerado (pyqtgraph).
- Iluminación hillshade configurable para resaltar la textura superficial.
- Colormap dorado estilo NanoSurf y otros colormaps perceptualmente uniformes (Crameri).
- Rotación, zoom y paneo con el ratón.
- Exporta la vista actual a PNG.

---

## Pestaña 4 — Resonancia

Análisis de curvas de resonancia del cantiléver (thermal tuning).

**Qué hace:**

- Carga una serie temporal de espectros de thermal tuning (archivos `.nid` ordenados cronológicamente).
- Extrae la **frecuencia de resonancia** f(t) y la masa efectiva m(t) del cantiléver.
- Calcula la **tasa de evaporación** dm/dt y ajusta la **ley d²** (evaporación limitada por difusión).
- Muestra gráficos de f(t), Δm(t) y el ajuste d² con R² e intervalo de tiempo de vida τ.
- Exporta la serie temporal a CSV.

---

## Pestaña 5 — Simulador

Gemelo digital del cantiléver AFM.

**Qué hace:**

- Simula el **ruido térmico** del cantiléver a temperatura ambiente a partir de k y f₀.
- Modela el **corrimiento de frecuencia** Δf por adición de masa Δm (sensado de masa).
- Permite explorar parámetros (constante de resorte, frecuencia de resonancia, temperatura, Q) y ver el efecto en la PSD de ruido y la sensibilidad de masa.
- Útil para calibración y diseño de experimentos de sensado.

---

## Pestaña 6 — Editor de figuras

Editor WYSIWYG para figuras de publicación.

**Qué hace:**

- Carga cualquier canal del archivo abierto y genera una figura de publicación.
- Configura **colormap** (Crameri: batlow, tokyo, vik, davos…), título, etiquetas de ejes y colorbar.
- Ajusta el **rango de color** (vmin / vmax) con sliders interactivos.
- Añade y arrastra **barra de escala física** (µm / nm) y anotaciones de texto.
- Previsualización en vivo; exporta a **PNG**, **SVG** o **PDF** de alta resolución.

---

## Pestaña 7 — Comparar

Comparación multi-archivo.

**Qué hace:**

- Carga 2 a 4 archivos AFM/KPFM simultáneamente.
- Muestra un panel fusionado con colorbar y escala compartidas (o una colorbar por panel si los barridos tienen rangos distintos).
- Permite seleccionar el canal a comparar en todos los archivos a la vez.
- Útil para comparar muestras tratadas vs. control, o el mismo sitio antes/después de un proceso.

---

## Atajos de teclado

| Acción | Atajo |
|--------|-------|
| Abrir archivo | `Ctrl+O` |
| Cambiar tema claro/oscuro | `Ctrl+T` |
| Exportar CSV | `Ctrl+E` |
| Cambiar pestaña siguiente | `Ctrl+Tab` |

---

## Archivos recientes y drag & drop

- La barra de menú guarda los **archivos recientes** para acceso rápido.
- Se puede **arrastrar y soltar** un archivo `.nid`, `.nhf` o `.gwy` directamente sobre la ventana principal para abrirlo.

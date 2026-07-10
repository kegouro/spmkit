# Guía de usuario — Fathom (GUI)

La GUI de spmkit es **Fathom**, un workspace de escritorio (PyQt6 + pyqtgraph) organizado en
**perspectivas** (no pestañas planas): cambias de *tarea*, no de pestaña, y cada perspectiva
muestra sólo los paneles que necesita. Una **paleta de comandos** (⌘K) da acceso a todo.

## Abrir la GUI

```bash
spmkit gui           # Fathom (por defecto)
spmkit gui --legacy  # la app clásica de 7 pestañas (conservada como fallback)
```

O desde Python:

```python
from spmkit.gui.app import run
run()
```

!!! note "Requisito"
    Instala el extra `gui`: `pip install "spmkit[gui]"`. Para detección de granos añade
    `grains` (scipy): `pip install "spmkit[gui,grains]"`.

## Abrir datos

- **Arrastra y suelta** un archivo sobre la ventana, o `Ctrl+O`.
- Fathom **inspecciona** el archivo y lo rutea solo: imágenes (`.nid`, `.nhf`, `.gwy`) van a
  las perspectivas de imagen; curvas/force-volume (`.jpk-force`, `.nid` de espectroscopía,
  y con el extra `afm`: QI/force-map de JPK, `.ibw`, HDF5…) van a las de fuerza. Si un
  archivo trae imagen **y** curvas, pregunta cómo abrirlo.

---

## Perspectivas

### Imagen
Visor de canales: elige canal, **nivela** (plano / polinomio / por filas), **colormap**, y
traza un **perfil de línea** arrastrando el ROI sobre la imagen. El panel *Análisis* grafica
el perfil y muestra rugosidad (Sa/Sq/Sz/Ssk/Sku) y **KPFM/CPD** para canales de potencial;
exporta el perfil a CSV.

### Granos
Detección de partículas sobre la topografía nivelada: **overlay** coloreado + estadística
(conteo, diámetro equivalente medio, cobertura, densidad por µm²). Ajusta tamaño mínimo y
altura relativa y pulsa **Detectar**. Requiere el extra `grains`.

### Espectral
**PSD radial** en log-log + **dimensión fractal** / exponente de Hurst / longitud de
correlación. Se recalcula al cambiar de canal.

### Curva de fuerza
La joya: navega curva a curva, ve el ajuste de contacto (Hertz / paraboloide / cono / DMT /
**JKR adhesivo**), módulo ± incertidumbre (**Monte Carlo** opcional), R², adhesión y disipación.
El **pipeline** (calibración, método de contacto *conjunto/umbral*, región de ajuste) es una
receta reproducible; todos los umbrales son editables. Botón **Exportar curva…** → CSV
científico (ajuste con unidades + datos separación/fuerza).

### SMFS (espectroscopía de molécula única)
Sobre la rama de **retracción**: detecta los eventos de ruptura por **prominencia** (no un
umbral ingenuo) y ajusta una **cadena polimérica** por evento — **WLC** (Marko-Siggia/Bouchiat)
o **FJC** (Langevin) — recuperando la longitud de contorno y de persistencia/Kuhn, con control
de calidad por R². Umbrales (R², prominencia, altura, temperatura, variante WLC) editables;
**histograma de contorno** de población y **exportar eventos** a CSV.

### Sintonía térmica
Ajusta el espectro de ruido térmico (SHO) para extraer **f₀, Q** y la constante de resorte
**k** por equipartición desde un canal espectral cargado.

### Mapa
Corre el pipeline por cada curva de un force-volume y arma **mapas de propiedades** (módulo,
adhesión, contacto…) + histograma. Rápido (vectorizado, CPU/GPU) con *fallback* al pipeline
para curvas de largo variable (QI). Botón **Exportar datos…** → CSV científico (metadatos +
estadística por propiedad + tabla por punto, con unidades y sin volcados de NaN).

### Batch
Procesa carpetas de curvas **y mapas** de fuerza y arma una tabla resumen científica (unidades
en los encabezados, celdas vacías en vez de NaN).

### Figura
Editor WYSIWYG de figuras de publicación: canal + colormap + título/ejes + barra de escala +
colorbar + **anotaciones de texto arrastrables** totalmente personalizables. Exporta PNG/SVG/PDF.

### Vista 3D
Superficie de topografía con iluminación (hillshade) y **exageración Z visual** (los datos
siguen físicos; el eje Z se muestra en nm/µm).

### Simulador
Gemelo digital educativo del cantiléver: cómo la masa añadida desplaza la resonancia y el
espectro de ruido térmico.

---

## Personalizar la apariencia

`Ctrl+Shift+A` (o la paleta → **Personalizar apariencia…**) abre un diálogo con **vista previa
en vivo**:

- **Tema** entre presets: Grafito (oscuro), Papel (claro), NanoSurf oro, Nord, Dracula,
  Solarized (oscuro/claro), Gruvbox — mostrados como tarjetas con sus propios colores.
- **Acento** personalizado (cualquier color).
- **Tamaño de fuente** (Compacto / Normal / Cómodo / Grande).

La elección se **persiste** entre sesiones. `Ctrl+Shift+L` alterna claro/oscuro rápido
preservando acento y fuente. El tema alimenta a la vez la app, pyqtgraph y matplotlib, así los
gráficos se sienten nativos.

---

## Proyectos, informes y exportación

- **Proyecto `.spmproj`** (`Ctrl+S` / *Abrir proyecto*): guarda el archivo abierto, los
  parámetros del pipeline y la perspectiva activa.
- **Informe** (`Ctrl+Shift+R`): genera un informe *pre-hecho* con gráficos en HTML y PDF (y
  LaTeX). También **Exportar todo** (mapas CSV, tabla por curva, resumen e informe).

---

## Atajos

| Acción | Atajo |
|--------|-------|
| Paleta de comandos | `Ctrl+K` |
| Abrir archivo | `Ctrl+O` |
| Guardar proyecto | `Ctrl+S` |
| Calcular mapa | `Ctrl+M` |
| Generar informe | `Ctrl+Shift+R` |
| Personalizar apariencia | `Ctrl+Shift+A` |
| Alternar tema claro/oscuro | `Ctrl+Shift+L` |
| Curva anterior / siguiente | `Ctrl+←` / `Ctrl+→` |

!!! tip "¿Extender Fathom?"
    Añadir una perspectiva o un formato nuevo es un trámite corto — ver
    [Extender spmkit y Fathom](extending.md).

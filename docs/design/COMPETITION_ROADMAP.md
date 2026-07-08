# Plan de competencia real vs JPK Data Processing y Nanosurf Analysis

Auditoría de spmkit/Fathom contra el informe de capacidades de JPK DP 4.2 y Nanosurf
Analysis/Report, con un roadmap priorizado para llegar a competir de verdad.

## Veredicto

spmkit está **más cerca de lo que parece**. La base científica es fuerte y validada
(lectura `.nid` a precisión de máquina, calibración InVOLS/k, punto de contacto robusto,
δ=Z−d, Hertz/paraboloide/cono/DMT, mapas de force-volume con *linked brushing*, rugosidad
areal, FFT/PSD, 3D, grains, informe HTML/PDF, API Python). El problema #1 **no es
capacidad, es descubribilidad**: muchas funciones existen pero están escondidas en la paleta
⌘K, sin botón ni panel visible — por eso "no se ven". El problema #2 son **dos dominios
enteros ausentes** (SMFS y step-fitting) y el **pegamento de flujo de lote** (filtrado/QC de
curvas + histogramas con ajuste).

## Lo que spmkit YA hace (corroboración)

| Capacidad JPK/ANA | spmkit | Nota |
|---|---|---|
| Calibración V→m→N (InVOLS, k, térmica) | ✅ | `core/analysis/calibration.py`, visible en pipeline |
| Punto de contacto automático | ✅ | ROV (Gavara) + umbral |
| Separación punta-muestra δ=Z−d | ✅ | op `tip_sample_separation` |
| Hertz / paraboloide / cono (Sneddon) / DMT | ✅ | `forcecurve.py` |
| **Rango de fit por región (click-drag)** | ✅ | checkbox "Región" en la curva — **escondido** |
| **Aplicar el fit de la zona de contacto a TODAS las curvas del mapa** | ✅ | `map_vm` usa el pipeline por curva cuando hay `fit_min` — **escondido** |
| Poisson configurable | ✅ | |
| Adhesión (mín/pull-off), disipación (área histéresis) | ✅ | Inspector + informe |
| Mapas de fuerza: visor + curva por pixel + mapas de propiedad | ✅ | perspectiva Mapa, CPU/GPU |
| Rugosidad (Sa/Sq/Sz areal), perfiles (cross-section), FFT/PSD, 3D, grains | ✅ | perspectivas Imagen/Espectral/3D/Granos |
| Batch multi-archivo | ✅ | perspectiva Batch, CLI `fbatch` |
| Export CSV/JSON/figuras + informe HTML/PDF/LaTeX | ✅ | |
| Scripting (API Python) | ✅ | **superior** a VBScript de ANA |
| Guardar/cargar proceso (`.spmproj` + Recipe YAML) | 🟡 | existe, no equivalente pleno a `.jpk-proc-force` |

## Brechas reales (prioridad ALTA del informe)

| Categoría | Estado | Falta |
|---|---|---|
| **Modelos de cadena (SMFS)** | ❌ ausente | WLC (Marko-Siggia + Bouchiat), FJC, extensibles, detección de eventos en retract, multi-pico, pinning. **Dominio bio-AFM/molécula única entero.** |
| **Step fitting** | ❌ ausente | Algoritmo Kerssemakers (tethers de membrana). |
| **Filtrado/QC de curvas** | ❌ ausente | Clasificar curvas por parámetros (umbral básico, dos grupos, keep/discard), expresiones booleanas sobre resultados. |
| **Histogramas de batch con ajuste Gaussiano** | 🟡 parcial | Histograma + fit Gaussiano simple/multi-pico de parámetros del lote. |
| **JKR / viscoelástico** | 🟡 experimental | Validar contra referencia (hoy flagged). |
| **Sneddon pirámide 4 caras, bottom-effect** | ❌ | Geometrías/correcciones que faltan. |
| **Suavizado** | 🟡 | Solo Savitzky-Golay orden fijo; falta Gaussiano, Boxcar, elegir orden. |
| **Mediciones manuales** | 🟡 | Distancia/ángulo entre puntos, altura al setpoint, snap-in, measure-slope. |
| **Filtros de imagen + correcciones de línea** | ❌ | median/lowpass/highpass/edge/invert; histfit, remove-lines. |
| **Export TIFF 16/32-bit** | ❌ | (PNG/SVG/PDF ya están). |

## Roadmap priorizado (por máximo salto competitivo / costo)

### Tanda 0 — Descubribilidad (S, la más barata y de mayor impacto inmediato)
Hacer visible el poder que ya existe. **No agrega capacidad, cierra la queja "no lo veo".**
- Botones visibles Abrir/Guardar ✅ (hecho).
- Renombrar/exponer "Región" → **"Zona de contacto"** con ayuda inline; botón "Aplicar a todo
  el mapa" junto a Calcular mapa.
- Panel "Mediciones" siempre visible (E±σ, R², adhesión, disipación, δmáx) en vez de solo Inspector.
- Toolbar contextual por perspectiva (los controles del panel central, hoy algo escondidos).
- Tour/onboarding de 1 pantalla y tooltips en todo.

### Tanda 1 — QC/filtrado de curvas + histogramas (M) — el pegamento del flujo de lote
- `core/analysis/curveqc.py`: clasificar curvas por parámetros (umbral ≥/≤, dos grupos,
  keep/discard); expresiones booleanas reusando el evaluador AST seguro que ya existe.
- Histogramas de parámetros del batch con **ajuste Gaussiano** (simple/multi-pico).
- Perspectiva Batch enriquecida: tabla + histograma + keep/discard por curva.

### Tanda 2 — SMFS: modelos de cadena (L) — el mayor salto de capacidad
- `core/analysis/chain.py`: **WLC** (Marko-Siggia + Bouchiat), **FJC**, extensibles (EWLC/EFJC).
- Detección de eventos de ruptura en la rama retract; ajuste **multi-pico**; **pinning** de L/lp.
- Salidas: contour length, persistence length, breaking force, loading rate.
- **Módulo Fathom nuevo** (perspectiva "Molécula única") — usa la extensibilidad de F4.
- Desbloquea bio-AFM / espectroscopía de molécula única (el fuerte de JPK).

### Tanda 3 — Step fitting (M)
- `core/analysis/steps.py`: algoritmo Kerssemakers (fondo suave + escalones), umbral de
  significancia, desactivar escalones; salidas position/height/plateau/step_count.

### Tanda 4 — Paridad de imagen (M)
- Filtros: median, lowpass (Gaussiano), highpass (unsharp), edge, invert.
- Correcciones de línea: histfit (polinomial por línea), remove-lines (interpolación).
- Herramientas: medir distancia/ángulo, histograma de alturas, crop.

### Tanda 5 — Completitud mecánica (M)
- Sneddon pirámide 4 caras; corrección bottom-effect (muestras delgadas).
- **Validar JKR/viscoelástico** (quitar el flag al validar contra referencia).
- Suavizado: Gaussiano + Boxcar + elegir orden SG.
- Export TIFF 16/32-bit; guardar/cargar proceso equivalente a `.jpk-proc-force`.

## Quick wins (≤1 día c/u)
1. Botones Abrir/Guardar ✅.
2. "Región" → "Zona de contacto" visible + botón "aplicar al mapa".
3. Panel Mediciones siempre visible.
4. Histograma con fit Gaussiano en Batch.
5. Filtros de imagen median/invert (numpy/scipy, triviales).

## Principio
Reutilizar el core validado y la extensibilidad de F4 (los dominios nuevos = módulos por
entry-point). Nada de features huérfanas: cada tanda deja algo **visible y testeado**.

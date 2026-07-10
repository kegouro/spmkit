<div align="center">

<img src="docs/images/brand/banner.png" alt="SPM-Kit Banner" width="100%">

# SPM-Kit: Core SDK para Microscopía de Sonda de Barrido

### Motor Numérico y Framework de Extensibilidad Abierta

[![CI](https://github.com/kegouro/spmkit/actions/workflows/ci.yml/badge.svg)](https://github.com/kegouro/spmkit/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-515%20passing-brightgreen.svg)](https://github.com/kegouro/spmkit/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-73%25-green.svg)](#validación-científica-y-cobertura)
[![PyPI](https://img.shields.io/pypi/v/spmkit.svg?color=2dd4bf)](https://pypi.org/project/spmkit/)
[![Python](https://img.shields.io/badge/python-3.11%20|%203.12-blue.svg)](https://pypi.org/project/spmkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**[Documentación Oficial](https://kegouro.github.io/spmkit/)** · [Fathom Workspace](#fathom-entorno-de-análisis-avanzado) · [Arquitectura](#arquitectura-del-software) · [Validación](#validación-científica-y-cobertura)

<br>
</div>

**SPM-Kit** es un marco de trabajo (*toolkit*) riguroso y de código abierto desarrollado en el **SPM Lab** de la Universidad Técnica Federico Santa María (UTFSM). Proporciona la infraestructura algorítmica y matemática necesaria para la decodificación, análisis espectral, nivelación y extracción de propiedades nanomecánicas a partir de datos de microscopía de sonda de barrido (AFM, KPFM).

---

## Fathom: Entorno de Análisis Avanzado

<div align="center">
<img src="docs/images/brand/fathom_banner.svg" alt="Fathom Workspace Banner" width="100%">
<br>


Mientras que `spmkit` actúa como la capa computacional subyacente, **Fathom** es el espacio de trabajo (*workspace*) interactivo insignia construido sobre su API. Fathom ha sido diseñado arquitectónicamente para sustituir herramientas propietarias de alto costo (como Nanosurf ANA y JPK Data Processing) en ecosistemas de investigación intensiva.

Para instanciar el entorno Fathom:

```bash
spmkit workspace [archivo_opcional]
```

### Capacidades Funcionales de Fathom

- **Pipeline de Ajuste Nanomecánico en Tiempo Real:** Ajuste algorítmico continuo para curvas de fuerza con modelos de contacto (Hertz, paraboloide, Sneddon cónico, DMT y **JKR adhesivo**) — módulo de Young con **incertidumbre por Monte Carlo**, radio de punta, corrección de Poisson, **método de detección de contacto** (ajuste conjunto robusto vs umbral), calibración (InVOLS y constante de resorte por ruido térmico) y ventanas de ajuste manual. Cada modelo entra al repositorio **solo si recupera parámetros conocidos** de datos sintéticos con ruido dentro de tolerancia (*gate* de recuperación numérica en `tests/validation`); la relajación viscoelástica SLS permanece marcada como experimental.
- **Espectroscopía de Fuerza de Molécula Única (SMFS):** detección de eventos de ruptura por **prominencia** (sin *thresholding* ingenuo) y ajuste de cadena polimérica por evento — **WLC** (Marko-Siggia + Bouchiat) y **FJC** (Langevin) — con control de calidad (R²) sobre la rama de retracción corregida de línea base, más histograma de longitud de contorno de población.
- **Exportación con Fidelidad Científica:** los mapas de fuerza, curvas individuales y lotes se exportan a CSV trazable con **cabecera de metadatos** (parámetros de análisis), **unidades físicas en cada columna** y estadística robusta por propiedad — sin volcados de `NaN` (las columnas sin datos se omiten con nota, los puntos fallidos quedan vacíos).
- **Topología de Mapeo de Volúmenes de Fuerza (*Force-Volume*):** Extracción de propiedades locales mapeadas a coordenadas espaciales, implementando *linked brushing* interactivo entre espectros y topografía.
- **Sistema Modular por Perspectivas:** Superando las interfaces monolíticas, Fathom emplea una estructura de vistas modulares (Perspectivas) que segrega lógicamente las áreas de trabajo: **Imagen** (topografía, perfiles de línea, rugosidad ISO 25178 y KPFM/CPD por sonda Kelvin), **Granos** (detección de partículas), **Espectral** (PSD radial, dimensión fractal), **Curva de Fuerza**, **Mapa** de force-volume, **SMFS** (eventos + cadena WLC/FJC), **Sintonía térmica** (f₀/Q/k por ruido térmico), **Batch**, **Figura**, **Vista 3D** y **Simulador**. Todo parámetro de análisis (umbrales, modelos, unidades) es **editable en la interfaz** — nada hardcodeado.
- **Framework de Extensibilidad Abierta:** nuevos **formatos**, **análisis** y **perspectivas** se registran por *entry-points* (`spmkit.plugins.v1`, `spmkit.gui.modules`) **sin tocar el núcleo** — la base para que `spmkit` sea un host multi-física y Fathom una de sus extensiones. Añadir un módulo es declarar un `ModuleSpec` (ver la [guía de extensión](https://kegouro.github.io/spmkit/extending/)).
- **Personalización Visual:** temas con presets (Grafito, Papel, NanoSurf oro, Nord, Dracula, Solarized, Gruvbox), color de acento y escala tipográfica con **vista previa en vivo**, persistentes entre sesiones.
- **Motor de Renderizado Dinámico:** Renderizado tridimensional interactivo con modelos de iluminación (*hillshade*) y exageración Z visual.

<div align="center">
<img src="docs/images/screenshot_viewer.png" alt="Fathom Interfaz Principal" width="100%">
<sub>Interfaz del Workspace Fathom (Renderizado con perfiles bilineales).</sub>
</div>

---

## Arquitectura del Software

El ecosistema adopta un paradigma estricto de separación de capas (Arquitectura Hexagonal/Clean Architecture), asegurando que el análisis matemático permanezca agnóstico respecto a la interfaz de usuario.

```mermaid
graph TD
    subgraph SPM-Kit Core [spmkit.core]
        IO[Módulo de Entrada/Salida]
        ANALYSIS[Algoritmos de Análisis]
        MODELS[Modelos de Datos Estandarizados]
        
        IO --> MODELS
        ANALYSIS --> MODELS
    end

    subgraph Presentación [spmkit.gui / spmkit.cli]
        CLI[Interfaz de Línea de Comandos]
        FATHOM[Fathom Workspace]
        
        CLI -.-> ANALYSIS
        FATHOM -.-> ANALYSIS
        FATHOM -.-> IO
    end

    EXT1[(Archivos .nid)] --> IO
    EXT2[(Archivos .gwy)] --> IO
    EXT3[(Archivos .jpk-force)] --> IO
```

- **Directorio Core:** El motor numérico se encuentra aislado en `[src/spmkit/core](./src/spmkit/core)`. Ninguna dependencia gráfica interactúa con esta capa, lo que permite su despliegue en clústeres de computación de alto rendimiento (*HPC*).
- **Directorio de Presentación:** La lógica de interacción, gestión de estado (*ViewModels*) y vistas de PyQt6 residen en `[src/spmkit/gui](./src/spmkit/gui)`.

---

## Ecosistema y Formatos de Archivo

El módulo de entrada y salida garantiza interoperabilidad de ciclo completo (*round-trip*) con las plataformas estandarizadas de la industria.

| Extensión | Formato Origen | Estado de Soporte |
|-----------|----------------|-------------------|
| `.nid` | NanoSurf Clásico | Validación Categórica (Lectura) |
| `.gwy` | Gwyddion | Lectura y Escritura Nativa |
| `.nhf` | NanoSurf HDF5 | Soporte Experimental |
| `.jpk-force` | JPK Instruments | Integración en Fathom |

---

## Validación Científica y Cobertura

La rigurosidad es el pilar de SPM-Kit. El decodificador de matrices binarias para archivos `.nid` ha sido sujeto a validaciones algorítmicas de control cruzado contra *Gwyddion*.

La matriz de pruebas demuestra una **correlación de precisión de máquina (1.000000)** en la conversión a unidades métricas físicas. Los informes de prueba y auditoría numérica pueden consultarse íntegramente en `[docs/VALIDATION.md](./docs/VALIDATION.md)` y en el subdirectorio de pruebas `[tests/validation/](./tests/validation)`.

Más allá del *round-trip* de formatos, cada modelo físico se somete a un **gate de recuperación numérica**: se generan datos sintéticos con parámetros conocidos y ruido controlado, y el ajuste debe recuperarlos dentro de tolerancia o no entra al repositorio (módulo de Young a <2% incluso con ruido gracias al ajuste conjunto del contacto; contorno/persistencia de WLC/FJC y E\*/adhesión de JKR igualmente validados).

Actualmente, el repositorio ejecuta una suite integral automatizada por GitHub Actions que valida **348 pruebas de núcleo y validación**, más una suite de **167 pruebas de GUI** (offscreen), en entornos estandarizados de Python 3.11 y 3.12.

---

## Guía de Despliegue e Instalación

El empaquetado de SPM-Kit es modular. Los investigadores pueden optar por instalar únicamente el motor de cálculo, o el ecosistema gráfico completo.

```bash
# Instalación del motor matemático (Recomendado para servidores/HPC)
pip install spmkit

# Instalación integral incluyendo Fathom Workspace (Recomendado para workstations)
pip install "spmkit[gui]"

# Instalación completa con todas las dependencias cruzadas (HDF5, Reportes, SciPy Grains)
pip install "spmkit[all]"
```

### Operaciones por Línea de Comandos

La interfaz de comandos proporciona tuberías (*pipelines*) de análisis directo sin sobrecarga gráfica:

```bash
spmkit info scan.nid                     # Extracción de metadatos instrumentales
spmkit roughness scan.nid -c Z-Axis      # Determinación de parámetros ISO 25178
spmkit convert scan.nid scan.gwy         # Transcripción a ecosistema Gwyddion
spmkit fbatch /datos -o resultados.csv   # Procesamiento distribuido de múltiples curvas
```

---

## Contribución Académica

Las aportaciones al código fuente son bienvenidas y sujetas a estrictas políticas de revisión. El análisis numérico reside exclusivamente en `src/spmkit/core/`. Se exige el cumplimiento integral de métricas estáticas mediante `mypy`, formateo determinista con `black` y cumplimiento de linters mediante `ruff`.

Referirse a `[CONTRIBUTING.md](./CONTRIBUTING.md)` para las pautas formales.

### Referencia Citacional

En el caso de utilizar SPM-Kit o Fathom para la obtención de resultados en publicaciones académicas, solicitamos citar el proyecto de acuerdo a los estándares definidos en `[CITATION.cff](./CITATION.cff)`.

<br>

<div align="center">

[![DOI](https://zenodo.org/badge/1270254374.svg)](https://zenodo.org/badge/latestdoi/1270254374)

<sub>Proyecto auspiciado y estructurado bajo el <b><a href="https://kegouro.github.io">Pharos Project</a></b> — Desarrollando infraestructura científica sin barreras computacionales.</sub>
<br>
<sub>José Labarca Baeza · Prof. Tomás Corrales | Licencia MIT © 2026</sub>

</div>

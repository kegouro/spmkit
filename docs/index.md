# spmkit

**Analizador open-source de datos AFM / KPFM para microscopía de sonda de barrido**

*Desarrollado en el SPM Lab de la Universidad Técnica Federico Santa María (UTFSM)*

[![CI](https://github.com/kegouro/spmkit/actions/workflows/ci.yml/badge.svg)](https://github.com/kegouro/spmkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/spmkit.svg?color=2dd4bf)](https://pypi.org/project/spmkit/)
[![Python](https://img.shields.io/badge/python-3.11%20|%203.12-blue.svg)](https://pypi.org/project/spmkit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/kegouro/spmkit/blob/main/LICENSE)

---

spmkit lee formatos **NanoSurf** (`.nid`, `.nhf`) y **Gwyddion** (`.gwy`) y entrega análisis listo para publicar: rugosidad ISO 25178, perfiles interactivos, KPFM y nanomecánica, con una CLI y una GUI científica completa.

Su lectura del `.nid` está **validada a precisión de máquina** contra Gwyddion.

![spmkit GUI](images/screenshot_viewer.png)

*Interfaz de spmkit — captura con datos sintéticos de ejemplo*

---

## ¿Qué puede hacer spmkit?

| Capacidad | Descripción |
|-----------|-------------|
| **Formatos** | Lee `.nid`, `.nhf`, `.gwy`; escribe `.gwy` (round-trip con Gwyddion) |
| **Rugosidad** | ISO 25178 (Sa, Sq, Sz, Ssk, Sku) + nivelación (plano / polinomio / filas) |
| **Perfiles** | Perfiles de línea interactivos con interpolación bilineal |
| **KPFM** | Potencial de contacto (CPD) y función de trabajo |
| **Nanomecánica** | Hertz / Sneddon → módulo de Young, adhesión, mapas de módulo |
| **Resonancia** | Thermal tuning → sensado de masa, tasa de evaporación, ley d² |
| **Vista 3D** | Superficie 3D interactiva con iluminación hillshade |
| **Espectral** | PSD radial, exponente de Hurst, dimensión fractal, longitud de correlación |
| **Simulador** | Gemelo digital del cantiléver: ruido térmico y corrimiento por masa |
| **Granos** | Detección de partículas y estadística de tamaños |
| **Figuras** | Editor WYSIWYG, colormaps científicos, barra de escala → PNG / SVG / PDF |
| **Comparar** | Fusiona 2–4 archivos con colorbar y escala compartidas |
| **Reportes** | Informe HTML completo (imprimible a PDF) + procesamiento por lotes |

---

## Instalación rápida

```bash
pip install spmkit
```

Para la interfaz gráfica:

```bash
pip install "spmkit[gui]"
```

Para todas las funcionalidades:

```bash
pip install "spmkit[all]"
```

Verifica la instalación:

```bash
spmkit --version
```

!!! tip "Primeros pasos"
    Consulta la [guía de instalación](getting-started.md) para instrucciones detalladas y ejemplos de primer uso.

---

## Links

- **Repositorio**: [github.com/kegouro/spmkit](https://github.com/kegouro/spmkit)
- **PyPI**: [pypi.org/project/spmkit](https://pypi.org/project/spmkit/)
- **Issues / feedback**: [github.com/kegouro/spmkit/issues](https://github.com/kegouro/spmkit/issues)
- **Licencia**: MIT © 2026 SPM Lab UTFSM — Prof. Tomás Corrales, José Labarca

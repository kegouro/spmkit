# Contribuir a spmkit

¡Gracias por tu interés! spmkit es desarrollado por el SPM Lab de la UTFSM y
recibe contribuciones de la comunidad.

## Preparar el entorno

```bash
git clone https://github.com/kegouro/spmkit
cd spmkit
uv pip install -e ".[dev,gui,hdf5,gwy,report,test-gui]"   # o pip
pre-commit install
```

> Los tests de la GUI requieren los extras `gui` + `test-gui` (PyQt6 + pytest-qt)
> y un entorno con Qt; en CI se omiten automáticamente (la ciencia sí se prueba).

## Principios de diseño

spmkit separa estrictamente tres capas (ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):

- **`core/`** — puro Python, sin dependencias de UI. Toda la ciencia vive aquí.
- **`cli/`** y **`gui/`** — solo orquestan/presentan; nunca implementan análisis
  ni tocan parsers directamente.

Si agregas análisis, va en `core/` con su test. La CLI/GUI solo lo invocan.

## Antes de abrir un PR

Todo lo que corre CI debe pasar localmente:

```bash
ruff check src tests      # lint
black --check src tests   # formato
mypy src                  # tipos
pytest                    # tests (+ cobertura)
```

- **Tests con datos**: usa datos sintéticos (ver `tests/conftest.py`). No
  subas archivos del instrumento (`reference/` está en `.gitignore`).
- **Confianza científica**: si tocas el manejo de datos (parsers, conversión
  de unidades, orientación), agrega o actualiza una prueba en
  `tests/validation/` y documenta el porqué. Ver [docs/VALIDATION.md](docs/VALIDATION.md).
- Mantén el estilo del código vecino (nombres, docstrings en español).

## Formatos e instrumentos nuevos

Para soportar un formato, agrega un parser en `core/io/` que devuelva un
`SPMData`, regístralo en `core/io/registry.py` y valídalo contra una
referencia conocida (otra herramienta o un archivo de especificación).

## Reportar bugs / pedir features

Usa las plantillas de issues. Incluye versión de spmkit, SO, y pasos para
reproducir (o un archivo sintético mínimo).

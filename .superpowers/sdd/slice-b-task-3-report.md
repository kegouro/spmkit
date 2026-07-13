# Slice B Task 3 — reporte

## Estado

PASS_WITH_CONCERNS. El contrato sintético `.nhf`, las dependencias y la documentación solicitada
quedaron implementados dentro de la allowlist. `docs/VALIDATION.md` es el archivo tracked que
corresponde a `docs/validation.md` en el brief; el filesystem local no distingue mayúsculas.

## RED

Comando:

```bash
.venv/bin/python -m pytest tests/core/test_nhf.py -q --no-cov
```

La primera ejecución detectó un error del fixture al construir bytes UTF-8 y el defecto esperado:
el `.nhf` no-HDF5 dejaba escapar `OSError: file signature not found`. Corregido únicamente el
fixture, la ejecución RED limpia quedó en `3 passed, 1 failed`, con el mismo `OSError` crudo.

Una revisión posterior estrechó el mensaje accionable. El test individual volvió a RED porque el
texto anterior no distinguía apertura/lectura de la clasificación de corrupción:

```text
Expected regex: no se pudo abrir o leer ... .nhf ... inválido|corrupto
Actual message: Archivo .nhf inválido o corrupto: ...
```

Se usaron dos enfoques: envolver únicamente `OSError` de h5py y, después, precisar el texto sin
ampliar la captura.

## GREEN

`load_nhf` conserva el recorrido HDF5 genérico, ignora datasets no 2D y transforma únicamente los
`OSError` de apertura/lectura en un `ValueError` accionable, conservando la causa. Un driver manual
por la API pública verificó:

```text
H1 ['Height'] Scan m (2, 2) True
H1_DATA True
H2 ValueError ... OSError
H3 TypeError fallo de programación simulado
```

H1 confirma despacho público y preservación; H2 confirma el error encadenado; H3 confirma que un
error de programación no queda oculto.

## Gates finales

```text
.venv/bin/python -m pytest tests/core/test_nhf.py -q --no-cov
.... [100%]

.venv/bin/ruff check src/spmkit/core/io/nhf.py tests/core/test_nhf.py
All checks passed!

.venv/bin/mypy src/spmkit/core/io/nhf.py
Success: no issues found in 1 source file

.venv/bin/python -m mkdocs build --strict
Documentation built successfully

git diff --check
sin salida
```

`site/` fue eliminado después de cada build. Como comprobación adicional ya iniciada antes de la
indicación de no ampliar suites, `tests/core -q --no-cov` terminó verde, con skips esperados y dos
warnings preexistentes de `grains.py`.

## Auto-revisión

- La API pública `spmkit.load` está cubierta con HDF5 sintético y sin archivos instrumentales.
- Datos, unidad, rangos, dirección, grupo, `source_path` y atributos bytes están verificados.
- HDF5 sin canales 2D y contenido no-HDF5 producen `ValueError` accionable.
- `nanosurf`/NSFopen se eliminaron de extras y `all`; NSFopen solo queda como opción futura.
- `.nhf` se describe como experimental y con contrato sintético, no validación instrumental.
- Python 3.11–3.12 y versión esperada 0.1.4 quedaron corregidos.
- No se tocaron registry, modelos, exporters, UI ni archivos de producto fuera de la allowlist.

## Concerns

- El contrato `.nhf` sigue siendo sintético; no demuestra compatibilidad con archivos reales ni
  con un oráculo externo.
- Una revisión de seguridad confirmó riesgos preexistentes del reader HDF5 genérico: datasets muy
  grandes/comprimidos pueden agotar recursos y HDF5 external/VDS puede leer rutas locales. Añadir
  límites o rechazos requeriría contrato y pruebas adversariales fuera del brief; no se cambió.
- `docs/index.md`, fuera de la allowlist, enumera `.nhf` sin el calificativo experimental. No se
  modificó.
- `docs/VALIDATION.md` conserva evidencia histórica específica preexistente fuera de la sección
  añadida. Su neutralización completa sería una tarea documental separada.

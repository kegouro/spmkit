# Slice B Task 4 — reporte

## Resultado

- Se añadió `profile` al CLI monolítico usando `_select_channel`, `_apply_level`,
  `profiles.line` y `to_csv`.
- `--x1` y `--y1` son opciones requeridas; toda coordenada se documenta en píxeles.
- Los errores de extracción de perfil se traducen a `typer.BadParameter`.
- El colormap por defecto de `figure` cambió de `batlow` a `gold`.
- Se añadieron journeys de librería y CLI sobre un `.gwy` real, temporal y reproducible.

## TDD

- RED: el journey focal ejecutó dos pruebas y falló en la tercera con
  `No such command 'profile'`.
- GREEN: el mismo comando terminó con `3 passed` tras el adaptador mínimo.

## Verificación

- `pytest tests/e2e/library/test_image_journey.py tests/e2e/cli/test_image_journey.py
  -q --no-cov`: 3 passed.
- `ruff check src/spmkit/cli/app.py tests/e2e`: limpio.
- `mypy src/spmkit/cli/app.py`: limpio.
- `pytest tests/core/test_cli_image.py -q --no-cov`: 13 passed.
- QA manual: ayuda visible, CSV `distance[m],height[m]` generado desde un `.gwy` real y
  coordenada fuera de rango rechazada con código 2.

## Auto-revisión y evidencia de depuración

- Hipótesis: la selección ambigua podía elegir un canal arbitrario. Evidencia: el journey real
  devuelve código 2 y exige `--direction/--group`.
- Hipótesis: un punto inválido podía filtrar un traceback. Evidencia: la QA devuelve código 2 y
  el mensaje `Punto fuera de los límites de la imagen`.
- Hipótesis: el export podía perder unidades o valores. Evidencia: CSV/JSON reabiertos coinciden
  con resultados en memoria y el PNG conserva firma válida.

No se encontraron concerns dentro del alcance. Dos gates globales ajenos al cambio quedaron
registrados: `make check` se detiene por el stub `types-PyYAML` ausente en el venv, y la suite GUI
completa produce un segfault preexistente en `tests/gui/test_map_vm.py:76`, también con Qt
offscreen. Los gates focales solicitados están verdes.

## Corrección de revisión

Se detectó que `tests/e2e/conftest.py` cambiaba globalmente el modo de importación de Pytest para
evitar la colisión entre los dos módulos `test_image_journey.py`. Se eliminó por completo ese hook
y se dieron identidades de paquete explícitas a `tests/e2e/library` y `tests/e2e/cli` mediante sus
respectivos `__init__.py`. Los dos journeys pasan juntos y la colección combinada de `tests/core`
y `tests/e2e` termina correctamente sin alterar la configuración global de Pytest.

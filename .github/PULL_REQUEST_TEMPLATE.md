## Descripción

Qué cambia y por qué.

## Tipo de cambio

- [ ] Bugfix
- [ ] Nueva feature
- [ ] Soporte de formato/instrumento
- [ ] Documentación
- [ ] Refactor / mantenimiento

## Checklist

- [ ] `ruff check src tests` pasa
- [ ] `black --check src tests` pasa
- [ ] `mypy src` pasa
- [ ] `pytest` pasa
- [ ] Agregué/actualicé tests (y `tests/validation/` si toqué manejo de datos)
- [ ] La lógica de análisis vive en `core/` (CLI/GUI solo orquestan)
- [ ] No subo datos del instrumento

## Notas de validación científica

Si cambiaste parsers/conversión/orientación, ¿cómo verificaste que sigue
siendo correcto?

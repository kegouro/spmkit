.PHONY: help install dev test lint format type check gui clean

help:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Instala el paquete (núcleo + CLI)
	uv pip install -e .

dev:  ## Instala con extras de desarrollo y hooks
	uv pip install -e ".[dev,gui,hdf5]"
	pre-commit install

test:  ## Corre los tests con cobertura
	pytest

lint:  ## Linting con ruff
	ruff check src tests

format:  ## Formatea con black + ruff
	black src tests
	ruff check src tests --fix

type:  ## Chequeo de tipos con mypy
	mypy src

check: lint type test  ## Lint + tipos + tests (lo que corre CI)

gui:  ## Lanza la interfaz gráfica
	spmkit gui

clean:  ## Limpia cachés y artefactos
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
	find . -type d -name __pycache__ -exec rm -rf {} +

run:  ## Lanza la app (script ligero)
	./run.sh

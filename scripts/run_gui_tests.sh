#!/usr/bin/env bash
# Corre la suite de GUI (tests/gui) **archivo por archivo**, cada uno en su propio proceso
# pytest. Es necesario porque Qt acumula recursos nativos en el teardown: correr muchos
# workspaces completos en un mismo proceso puede segfaultear al finalizar (aunque los
# tests pasen). Aislando por archivo, cada proceso arranca limpio y el resultado es fiable.
#
# Uso:
#   QT_QPA_PLATFORM=offscreen scripts/run_gui_tests.sh          # local (usa `python`)
#   PYTHON=.venv/bin/python scripts/run_gui_tests.sh            # local con venv explícito
#   uv run bash scripts/run_gui_tests.sh                        # CI (uv provee `python`)
#
# Cada archivo se corre con una cota dura de tiempo (si `timeout` está disponible) para que
# un test colgado no paralice el CI: se marca como fallo y el log muestra cuál fue.
# Sale con código != 0 si algún archivo falla o se cuelga.
set -u

PYTHON="${PYTHON:-python}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
LIMIT="${GUI_TEST_TIMEOUT:-120}"

TIMEOUT_BIN=""
command -v timeout >/dev/null 2>&1 && TIMEOUT_BIN="timeout ${LIMIT}"

echo "Python: $("$PYTHON" -c 'import sys; print(sys.executable)')"
echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM · timeout=${TIMEOUT_BIN:-<none>}"

failed=""
for f in tests/gui/test_*.py; do
  echo "▶ $f"
  # -o addopts="" descarta el --cov global (coverage por-archivo se pisaría); faulthandler
  # off silencia el volcado benigno del teardown de Qt.
  if $TIMEOUT_BIN "$PYTHON" -m pytest "$f" -o addopts="" --no-cov -q -p no:faulthandler; then
    echo "  ok   $f"
  else
    code=$?
    [ "$code" -eq 124 ] && echo "  TIMEOUT (${LIMIT}s) $f" || echo "  FAIL ($code) $f"
    failed="$failed $f"
  fi
done

if [ -n "$failed" ]; then
  echo "GUI tests fallaron/colgaron en:$failed"
  exit 1
fi
echo "GUI tests: todos los archivos pasaron."

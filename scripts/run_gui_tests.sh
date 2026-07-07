#!/usr/bin/env bash
# Corre la suite de GUI (tests/gui) **archivo por archivo**, cada uno en su propio proceso
# pytest. Necesario por dos rarezas de Qt en headless:
#
#   1. Teardown: Qt puede segfaultear al destruir sus objetos C++ en el shutdown del
#      intérprete (sobre todo en Linux), *después* de que los tests pasaron. pytest ya
#      escribió sus resultados (JUnit XML) en `sessionfinish`, antes de ese crash — así que
#      si el XML confirma que todo pasó, aceptamos el archivo aunque el proceso salga 139.
#   2. Acumulación: correr muchos workspaces completos en un mismo proceso agrava (1).
#      Aislar por archivo hace que cada proceso arranque limpio.
#
# Un **timeout** (test colgado) o un crash **sin** XX válido sí cuentan como fallo real.
#
# Uso:
#   QT_QPA_PLATFORM=offscreen scripts/run_gui_tests.sh          # local (usa `python`)
#   PYTHON=.venv/bin/python scripts/run_gui_tests.sh            # local con venv explícito
#   uv run bash scripts/run_gui_tests.sh                        # CI (uv provee `python`)
set -u

PYTHON="${PYTHON:-python}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
LIMIT="${GUI_TEST_TIMEOUT:-120}"

TIMEOUT_BIN=""
command -v timeout >/dev/null 2>&1 && TIMEOUT_BIN="timeout ${LIMIT}"

echo "Python: $("$PYTHON" -c 'import sys; print(sys.executable)')"
echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM · timeout=${TIMEOUT_BIN:-<none>}"

# ¿El JUnit XML confirma que corrieron tests y ninguno falló/erró? (código 0 = sí)
_xml_all_passed() {
  "$PYTHON" - "$1" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    sys.exit(1)
suites = root.findall('.//testsuite') or ([root] if root.tag == 'testsuite' else [])
tests = sum(int(s.get('tests', 0)) for s in suites)
bad = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
sys.exit(0 if tests > 0 and bad == 0 else 1)
PY
}

# Devuelve 0 (ok) / 1 (fallo) / 2 (timeout) para un archivo.
_run_one() {
  local f="$1" xml code
  xml="$(mktemp)"
  $TIMEOUT_BIN "$PYTHON" -m pytest "$f" -o addopts="" --no-cov -q -p no:faulthandler \
    --junit-xml="$xml"
  code=$?
  if [ "$code" -eq 0 ]; then rm -f "$xml"; return 0; fi
  if [ "$code" -eq 124 ]; then rm -f "$xml"; return 2; fi  # timeout → cuelgue real
  if [ -s "$xml" ] && _xml_all_passed "$xml"; then
    rm -f "$xml"
    echo "  (salida $code tras pasar — segfault de teardown de Qt; se acepta)"
    return 0
  fi
  rm -f "$xml"
  return 1
}

failed=""
for f in tests/gui/test_*.py; do
  echo "▶ $f"
  _run_one "$f"
  case $? in
    0) echo "  ok   $f" ;;
    2) echo "  TIMEOUT (${LIMIT}s) $f"; failed="$failed $f" ;;
    *) echo "  FAIL $f"; failed="$failed $f" ;;
  esac
done

if [ -n "$failed" ]; then
  echo "GUI tests fallaron/colgaron en:$failed"
  exit 1
fi
echo "GUI tests: todos los archivos pasaron."

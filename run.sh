#!/usr/bin/env bash
# run.sh — lanza spmkit (GUI) localmente. Crea el venv e instala la primera vez;
# después solo abre la app. Uso:  ./run.sh   (o  ./run.sh info archivo.nid  para la CLI)
set -e
cd "$(dirname "$0")"

VENV=.venv
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "▸ Creando entorno virtual (.venv)…"
  python3 -m venv "$VENV"
  echo "▸ Instalando spmkit + extras (gui, gwy, hdf5, grains, report)…"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -e ".[gui,gwy,hdf5,grains,report]"
fi

if [ "$#" -gt 0 ]; then
  exec "$VENV/bin/spmkit" "$@"   # pasa argumentos a la CLI:  ./run.sh roughness scan.nid
else
  echo "▸ Abriendo spmkit…"
  exec "$VENV/bin/spmkit" gui
fi

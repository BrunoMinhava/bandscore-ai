#!/usr/bin/env bash
# Arranca o BandScore AI em desenvolvimento: backend FastAPI + Vite + Electron.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() { kill 0 2>/dev/null; }
trap cleanup EXIT

(
  cd "$ROOT/backend"
  .venv/bin/uvicorn app.main:app --port 8765 --reload
) &

cd "$ROOT/frontend"
# ELECTRON_RUN_AS_NODE vem definida nos terminais do VSCode e faria o
# Electron arrancar como Node puro, sem API de janelas
env -u ELECTRON_RUN_AS_NODE npm run electron:dev

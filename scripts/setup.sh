#!/usr/bin/env bash

set -euo pipefail

echo "=== Setup de Cimiento ==="

# Backend
echo "Instalando dependencias Python..."
pushd backend >/dev/null
if command -v uv &> /dev/null; then
    uv sync --all-extras
else
    echo "uv no encontrado. Instalando entorno virtual con pip..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
fi
popd >/dev/null

# Frontend
echo "Instalando dependencias frontend..."
pushd frontend >/dev/null
npm install
popd >/dev/null

# Infra
echo "Levantando servicios con Docker Compose..."
pushd infra/docker >/dev/null
docker compose up -d
popd >/dev/null

# Ollama
if command -v ollama &> /dev/null; then
    echo "Descargando modelos Ollama del proyecto..."
    ./infra/ollama/pull-models.sh
else
    echo "Ollama no está instalado; omitiendo descarga automática de modelos."
fi

echo "=== Setup completado ==="
echo "Siguientes pasos sugeridos:"
echo "  - cd backend && uv run pytest"
echo "  - cd frontend && npm run build"
echo "  - revisar docs/installation/README.md para ajustes por hardware"

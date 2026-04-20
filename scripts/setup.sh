#!/usr/bin/env bash
# Setup inicial del proyecto
set -e

echo "=== Setup de Cimiento ==="

# Backend
echo "Instalando dependencias Python..."
cd backend
if command -v uv &> /dev/null; then
    uv sync --all-extras
else
    echo "uv no encontrado. Instalando con pip..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
fi
cd ..

# Infra
echo "Levantando servicios con Docker Compose..."
cd infra/docker
docker compose up -d
cd ../..

# Ollama
echo "Descargando modelos LLM..."
sleep 5
./infra/ollama/pull-models.sh

echo "=== Setup completado ==="
echo "Próximo paso: cd frontend && npm create vite@latest . -- --template react-ts"

#!/usr/bin/env bash
# =============================================================================
# Cimiento — Activar GPU AMD (Radeon RX 6600) en Ollama
# =============================================================================
# Este script aplica la configuración necesaria para que Ollama use la GPU AMD
# Navi 23 (RX 6600) mediante ROCm con el override de GFX versión.
#
# REQUISITO: ejecutar con sudo
#
# USO:
#   sudo bash scripts/setup_ollama_gpu.sh
#
# VERIFICACIÓN posterior:
#   journalctl -u ollama -n 20 -f   # buscar "GPU" o "VRAM"
#   curl -s http://localhost:11434/api/ps | python3 -m json.tool
# =============================================================================

set -euo pipefail

OVERRIDE_DIR="/etc/systemd/system/ollama.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/gpu.conf"

echo "==> Creando directorio de override: ${OVERRIDE_DIR}"
mkdir -p "${OVERRIDE_DIR}"

echo "==> Escribiendo configuración GPU..."
cat > "${OVERRIDE_FILE}" << 'EOF'
[Service]
# AMD Radeon RX 6600 — Navi 23 (GFX 10.3.0)
# HSA_OVERRIDE_GFX_VERSION fuerza el reconocimiento ROCm para esta GPU
Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"

# Permitir 2 modelos paralelos (7B extractor + 14B validador simultáneos)
# Con 8 GB VRAM: 7B q4 (~4.3 GB) + parcial 14B o ambos 7B
Environment="OLLAMA_NUM_PARALLEL=2"

# Mantener hasta 2 modelos cargados en VRAM para evitar swapping
Environment="OLLAMA_MAX_LOADED_MODELS=2"

# Contexto de 8k tokens (suficiente para el flujo de diseño)
Environment="OLLAMA_CONTEXT_LENGTH=8192"

# Flash attention — reduce VRAM del KV cache ~50%
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF

echo "==> Recargando systemd..."
systemctl daemon-reload

echo "==> Reiniciando Ollama..."
systemctl restart ollama

echo ""
echo "==> Esperando 5 segundos para que Ollama arranque..."
sleep 5

echo "==> Estado del servicio:"
systemctl status ollama --no-pager | head -15

echo ""
echo "==> VERIFICAR VRAM después de cargar un modelo:"
echo "    ollama run qwen2.5:7b-instruct-q4_K_M 'Hola'"
echo "    curl -s http://localhost:11434/api/ps | python3 -m json.tool"
echo "    (size_vram > 0 confirma uso de GPU)"

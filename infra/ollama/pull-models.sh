#!/usr/bin/env bash
# Descarga los modelos que usa Cimiento
set -e

echo "Descargando Qwen 2.5 7B Instruct (chat)..."
ollama pull qwen2.5:7b-instruct-q4_K_M

echo "Descargando nomic-embed-text (embeddings para RAG)..."
ollama pull nomic-embed-text

echo "Modelos descargados correctamente."
ollama list

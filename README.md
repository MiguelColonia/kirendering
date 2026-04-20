# Cimiento

Copiloto local de anteproyecto residencial. Combina razonamiento conversacional (Ollama + LangGraph), optimización espacial (OR-Tools) y generación BIM abierta (IfcOpenShell), ejecutándose íntegramente en local.

## Stack

- **Backend**: Python 3.11+, FastAPI, OR-Tools, IfcOpenShell, LangGraph, Ollama
- **Frontend**: React + TypeScript + Vite, IFC.js, Konva
- **Infra**: Docker Compose, Qdrant (RAG), PostgreSQL + PostGIS

## Estado actual

Fase 1 — Solver aislado.

## Setup rápido

Ver `docs/architecture/setup.md`.

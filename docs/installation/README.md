# Instalación / Installation

## Español

Este directorio reúne las guías de instalación de Cimiento para nuevo hardware. Empiece siempre por identificar la clase de máquina donde va a desplegar el sistema.

### Cómo elegir tu guía según hardware

- **Hardware AMD con GPU dedicada** y objetivo de usar aceleración local para render o IA: [installation-amd.md](installation-amd.md)
- **Hardware Nvidia con GPU dedicada** y objetivo de usar CUDA: [installation-nvidia.md](installation-nvidia.md)
- **Sin GPU dedicada** o entorno de CI / pruebas: [installation-cpu-only.md](installation-cpu-only.md)

### Requisitos comunes

- Linux x86_64.
- Acceso administrativo para instalar drivers, Docker y dependencias del sistema.
- Python 3.11+.
- Node.js 22 para el frontend.
- Docker Engine + Docker Compose plugin.
- Blender 4.x para el pipeline de render.
- Ollama para los modelos locales.

### Orden recomendado de trabajo

1. Leer la guía específica de hardware.
2. Instalar drivers y aceleración antes de tocar Ollama o Docker.
3. Instalar `uv`, dependencias Python y frontend.
4. Descargar los modelos locales.
5. Verificar backend, frontend y render base.
6. Elegir después si el despliegue será desarrollo o producción.

## Deutsch

Dieses Verzeichnis enthaelt die Installationsanleitungen fuer Cimiento auf neuer Hardware. Der erste Schritt ist immer die Auswahl der passenden Anleitung fuer die Zielmaschine.

### So waehlen Sie die passende Anleitung

- **AMD-Hardware mit dedizierter GPU** und geplanter lokaler Beschleunigung fuer KI oder Render: [installation-amd.md](installation-amd.md)
- **Nvidia-Hardware mit dedizierter GPU** und geplanter CUDA-Nutzung: [installation-nvidia.md](installation-nvidia.md)
- **Keine dedizierte GPU** oder CI-/Testumgebung: [installation-cpu-only.md](installation-cpu-only.md)

### Gemeinsame Voraussetzungen

- Linux x86_64.
- Administrativer Zugriff fuer Treiber, Docker und Systempakete.
- Python 3.11+.
- Node.js 22 fuer das Frontend.
- Docker Engine + Docker Compose Plugin.
- Blender 4.x fuer den Render-Pfad.
- Ollama fuer die lokalen Modelle.

### Empfohlene Reihenfolge

1. Die passende Hardware-Anleitung lesen.
2. Treiber und Beschleunigung zuerst installieren, danach erst Ollama oder Docker.
3. `uv`, Python-Abhaengigkeiten und Frontend installieren.
4. Lokale Modelle herunterladen.
5. Backend, Frontend und den Basis-Render pruefen.
6. Erst danach zwischen Entwicklungs- und Produktionsbetrieb unterscheiden.
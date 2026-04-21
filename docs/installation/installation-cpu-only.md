# Instalación CPU-only / CPU-only-Installation

## Español

### Advertencia de alcance

Esta guía está pensada para desarrollo, CI, pruebas funcionales o mantenimiento ligero. Cimiento puede arrancar sin GPU dedicada, pero con limitaciones claras:

- los LLMs pueden caer a **1-3 tokens por segundo**,
- el render fotorrealista local no es una opción práctica,
- la experiencia sigue siendo funcional para API, frontend, BIM, RAG e ingesta visual de forma limitada.

Si necesita render de presentación real, utilice otra máquina con GPU o un servicio cloud aprobado por su política interna.

### 1. Requisitos base

- Linux x86_64.
- 16 GB RAM como mínimo; 32 GB recomendados incluso sin GPU.
- Python 3.11+.
- Node.js 22.
- Docker Engine + Docker Compose plugin.
- Blender 4.x si quiere validar el pipeline base, aceptando que será lento.

### 2. Instalar dependencias del sistema

```bash
sudo apt update
sudo apt install -y git curl wget ca-certificates build-essential python3 python3-venv python3-pip nodejs npm blender docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### 3. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

Modelos recomendados para validar el entorno:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
```

Modelos más pesados como `14b` o `qwen2.5vl:7b` siguen siendo posibles, pero con latencias mucho mayores.

### 4. Instalar `uv` y dependencias del proyecto

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l

cd backend
uv sync --all-extras

cd ../frontend
npm install
```

### 5. Primera ejecución

Desarrollo local:

```bash
cd infra/docker
docker compose up --build -d
```

Validación rápida:

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py

cd ../frontend
npm run build
```

### 6. Qué esperar realmente

- Backend, frontend, CRUD de proyectos y visor IFC: funcionales.
- Chat con LLM: usable, pero lento.
- RAG normativo: funcional, aunque condicionado por la velocidad del embedding/modelos.
- Ingesta visual: posible, pero más lenta.
- Render fotorrealista: **no viable de forma práctica** en CPU para uso diario.

### 7. Troubleshooting

#### Todo funciona, pero es demasiado lento

- Es el comportamiento esperado en CPU-only.
- Use modelos 7B y limite pruebas a casos pequeños.

#### El render tarda varios minutos o no merece la pena

- No insista en CPU-only para presentaciones.
- Derive render a un host con GPU o a un runner externo aprobado.

#### Falta memoria RAM

- Cierre modelos de Ollama no usados.
- Evite abrir simultáneamente chat, embeddings y render en la misma sesión.

---

## Deutsch

### Hinweis zum Geltungsbereich

Diese Anleitung ist fuer Entwicklung, CI, funktionale Tests oder leichtes Maintenance gedacht. Cimiento laeuft auch ohne dedizierte GPU, aber mit klaren Einschraenkungen:

- LLMs fallen oft auf **1-3 Tokens pro Sekunde**,
- lokales fotorealistisches Rendering ist praktisch nicht sinnvoll,
- API, Frontend, BIM, RAG und visuelle Planaufnahme bleiben grundsaetzlich nutzbar.

Wenn Praesentationsrender benoetigt werden, sollte eine zweite Maschine mit GPU oder ein freigegebener Cloud-Weg genutzt werden.

### 1. Grundvoraussetzungen

- Linux x86_64.
- Mindestens 16 GB RAM, empfohlen sind 32 GB auch ohne GPU.
- Python 3.11+.
- Node.js 22.
- Docker Engine + Docker Compose Plugin.
- Blender 4.x nur fuer langsame Basispruefungen des Render-Pfads.

### 2. Systemabhaengigkeiten installieren

```bash
sudo apt update
sudo apt install -y git curl wget ca-certificates build-essential python3 python3-venv python3-pip nodejs npm blender docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### 3. Ollama installieren

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

Empfohlene Modelle fuer die erste Validierung:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
```

Schwerere Modelle wie `14b` oder `qwen2.5vl:7b` sind moeglich, aber deutlich langsamer.

### 4. `uv` und Projektabhaengigkeiten installieren

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l

cd backend
uv sync --all-extras

cd ../frontend
npm install
```

### 5. Erster Start

Lokale Entwicklung:

```bash
cd infra/docker
docker compose up --build -d
```

Schnellvalidierung:

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py

cd ../frontend
npm run build
```

### 6. Realistische Erwartungen

- Backend, Frontend, Projekt-CRUD und IFC-Viewer: nutzbar.
- Chat mit LLM: verwendbar, aber langsam.
- Norm-RAG: funktional, jedoch durch CPU-Leistung begrenzt.
- Visuelle Planaufnahme: moeglich, aber traeger.
- Fotorealistisches Rendering: **fuer den Alltagsbetrieb nicht praktikabel**.

### 7. Typische Probleme

#### Alles funktioniert, aber es ist zu langsam

- Das ist im CPU-only-Betrieb erwartbar.
- Fuer Tests zuerst 7B-Modelle und kleine Faelle verwenden.

#### Rendering dauert sehr lange oder lohnt sich nicht

- CPU-only ist kein sinnvoller Produktionsweg fuer Praesentationsrender.
- Rendering auf einen GPU-Host oder freigegebenen externen Runner auslagern.

#### RAM reicht nicht aus

- Nicht benoetigte Ollama-Modelle entladen.
- Chat, Embeddings und Render nicht gleichzeitig in grossen Lastprofilen fahren.
# Instalación AMD / AMD-Installation

## Español

### Alcance

Esta es la guía de referencia para el hardware validado del desarrollador original: **Ryzen 7 5700G + Radeon RX 6600 (8 GB VRAM) en Linux**. Es la ruta prioritaria para ejecutar Cimiento de forma local con aceleración AMD.

### Prerrequisitos del sistema

- Distribución recomendada: **Ubuntu 24.04 LTS** o derivada equivalente.
- Kernel recomendado: **6.8 o superior**.
- 32 GB RAM recomendados.
- Docker Engine + Docker Compose plugin.
- Blender 4.x.
- Acceso `sudo`.

### 1. Preparar el sistema base

```bash
sudo apt update
sudo apt install -y git curl wget ca-certificates build-essential python3 python3-venv python3-pip nodejs npm blender docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Cierre sesión y vuelva a entrar para que el grupo `docker` tenga efecto.

### 2. Instalar ROCm

Ruta práctica verificada para el host original:

```bash
sudo apt update
sudo apt install -y rocm
sudo usermod -aG render,video $USER
```

Después de reiniciar sesión, exporte el override necesario para GPUs AMD no oficialmente soportadas por ROCm:

```bash
echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.bashrc
source ~/.bashrc
```

Verificación básica:

```bash
rocminfo | grep -i gfx
```

Si `rocminfo` no muestra la GPU o ROCm falla de forma estable, pase directamente al fallback Vulkan descrito más abajo.

### 3. Alternativa Vulkan si ROCm falla

Si ROCm no es viable en su máquina:

- mantenga Blender con backend Vulkan o CPU según estabilidad real,
- acepte que el render fotorrealista y algunos modelos locales tendrán peor rendimiento,
- considere separar IA y render en otra máquina AMD/Nvidia o usar cloud opt-in solo para render.

Comprobación básica de Vulkan:

```bash
vulkaninfo | head
```

Si `vulkaninfo` no está instalado:

```bash
sudo apt install -y vulkan-tools
```

### 4. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

En otra terminal, descargue los modelos del proyecto:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
ollama pull qwen2.5vl:7b
```

Si quiere una reserva ligera para experimentos de visión o fallback manual:

```bash
ollama pull moondream
```

### 5. Instalar `uv` y dependencias Python

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l
```

Obtenga el repositorio en la nueva máquina y entre en él. Después:

```bash
cd backend
uv sync --all-extras
```

Frontend:

```bash
cd ../frontend
npm install
```

### 6. Configurar Docker y Docker Compose

Para desarrollo:

```bash
cd ../infra/docker
docker compose up --build -d
```

Para desarrollo con servicios IA opcionales:

```bash
cd ../infra/docker
docker compose --profile ai up -d
```

### 7. Primera ejecución y verificación

Backend:

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py
```

Frontend:

```bash
cd frontend
npm run build
```

Render base:

```bash
cd backend
uv run python scripts/test_render_manual.py --ifc data/outputs/rectangular_simple.ifc --device AUTO
```

Qué debe esperar:

- API respondiendo en `/health`.
- Frontend compilando sin errores.
- IFC de prueba exportable y render base generando PNGs.
- Ollama accesible con `ollama list`.

### 8. Troubleshooting común

#### ROCm no detecta la RX 6600

- Verifique `HSA_OVERRIDE_GFX_VERSION=10.3.0`.
- Compruebe pertenencia a grupos `render` y `video`.
- Reinicie sesión o la máquina antes de darlo por fallido.

#### Ollama usa demasiada RAM o va demasiado lento

- Cierre otros modelos residentes.
- Empiece con `qwen2.5:7b-instruct-q4_K_M` para validar el entorno.
- Acepte que `14b` puede necesitar offloading parcial.

#### Blender renderiza en CPU

- Compruebe ROCm primero.
- Si ROCm no es estable, asuma fallback Vulkan/CPU y tiempos de render mayores.

#### Docker no puede hablar con Ollama del host

- Use `host.docker.internal` con `extra_hosts` en producción.
- En local simple, levante Ollama en el mismo host fuera de contenedores.

---

## Deutsch

### Geltungsbereich

Diese Anleitung ist die Referenz fuer die validierte Entwickler-Hardware: **Ryzen 7 5700G + Radeon RX 6600 (8 GB VRAM) unter Linux**. Sie ist der bevorzugte Weg fuer den lokalen Betrieb von Cimiento auf AMD.

### Systemvoraussetzungen

- Empfohlene Distribution: **Ubuntu 24.04 LTS** oder vergleichbare Ableitung.
- Empfohlener Kernel: **6.8 oder neuer**.
- 32 GB RAM empfohlen.
- Docker Engine + Docker Compose Plugin.
- Blender 4.x.
- `sudo`-Zugriff.

### 1. Basissystem vorbereiten

```bash
sudo apt update
sudo apt install -y git curl wget ca-certificates build-essential python3 python3-venv python3-pip nodejs npm blender docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Danach ab- und wieder anmelden, damit die Docker-Gruppenmitgliedschaft aktiv wird.

### 2. ROCm installieren

Praktischer, auf dem Referenzhost genutzter Weg:

```bash
sudo apt update
sudo apt install -y rocm
sudo usermod -aG render,video $USER
```

Nach der neuen Anmeldung den noetigen Override fuer nicht offiziell unterstuetzte AMD-GPUs setzen:

```bash
echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.bashrc
source ~/.bashrc
```

Grundpruefung:

```bash
rocminfo | grep -i gfx
```

Wenn `rocminfo` die GPU nicht sauber meldet oder ROCm instabil bleibt, direkt zum Vulkan-Fallback wechseln.

### 3. Vulkan-Fallback, falls ROCm scheitert

Wenn ROCm auf dem Zielsystem nicht tragfaehig ist:

- Blender ueber Vulkan oder CPU betreiben,
- mit schlechterer Performance fuer Render und lokale Modelle rechnen,
- bei Bedarf KI oder Render auf eine andere Maschine oder einen Cloud-Opt-in auslagern.

Grundpruefung fuer Vulkan:

```bash
vulkaninfo | head
```

Falls `vulkaninfo` fehlt:

```bash
sudo apt install -y vulkan-tools
```

### 4. Ollama installieren

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

In einer zweiten Shell die Projektmodelle laden:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
ollama pull qwen2.5vl:7b
```

Optional fuer leichte Vision-Experimente oder einen manuellen Fallback:

```bash
ollama pull moondream
```

### 5. `uv` und Python-Abhaengigkeiten installieren

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l
```

Repository auf die neue Maschine bringen und dann:

```bash
cd backend
uv sync --all-extras
```

Frontend:

```bash
cd ../frontend
npm install
```

### 6. Docker und Docker Compose nutzen

Entwicklungsmodus:

```bash
cd ../infra/docker
docker compose up --build -d
```

Entwicklungsmodus mit optionalen KI-Diensten:

```bash
cd ../infra/docker
docker compose --profile ai up -d
```

### 7. Erster Start und Verifikation

Backend:

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py
```

Frontend:

```bash
cd frontend
npm run build
```

Basis-Render:

```bash
cd backend
uv run python scripts/test_render_manual.py --ifc data/outputs/rectangular_simple.ifc --device AUTO
```

Erwartetes Ergebnis:

- API antwortet unter `/health`.
- Das Frontend baut ohne Fehler.
- Das Test-IFC kann exportiert und als Basis-Render in PNGs umgesetzt werden.
- `ollama list` zeigt die geladenen Modelle.

### 8. Typische Probleme

#### ROCm erkennt die RX 6600 nicht

- `HSA_OVERRIDE_GFX_VERSION=10.3.0` pruefen.
- Gruppen `render` und `video` kontrollieren.
- Nach Gruppen- oder Treiberaenderungen neu anmelden oder neu starten.

#### Ollama ist zu langsam oder braucht zu viel RAM

- Nicht benoetigte Modelle entladen.
- Zuerst mit `qwen2.5:7b-instruct-q4_K_M` verifizieren.
- Bei `14b` partielles Offloading einkalkulieren.

#### Blender rendert nur auf CPU

- ROCm zuerst ueberpruefen.
- Wenn ROCm nicht stabil ist, CPU/Vulkan-Fallback bewusst akzeptieren.

#### Docker erreicht Ollama auf dem Host nicht

- In Produktion `host.docker.internal` plus `extra_hosts` verwenden.
- Fuer lokale Tests Ollama zunaechst direkt auf dem Host betreiben.
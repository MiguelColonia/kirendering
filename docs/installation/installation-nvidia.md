# Instalación Nvidia / Nvidia-Installation

> **AVISO:** Esta guía está basada en documentación oficial de Nvidia, CUDA y Ollama, pero no ha sido probada empíricamente por el equipo de Cimiento. Si encuentras discrepancias, abre una issue interna o propone una mejora a esta guía.
>
> **HINWEIS:** Diese Anleitung basiert auf offizieller Nvidia-, CUDA- und Ollama-Dokumentation, wurde aber vom Cimiento-Team nicht empirisch verifiziert. Wenn Sie Abweichungen finden, melden Sie diese bitte intern oder schlagen Sie eine Verbesserung der Anleitung vor.

## Español

### Prerrequisitos

- Linux x86_64, preferiblemente Ubuntu 24.04 LTS.
- Driver Nvidia propietario instalado.
- Recomendación conservadora: **branch 550 o superior**.
- GPU dedicada Nvidia con VRAM suficiente para los modelos previstos.
- Docker Engine + Docker Compose plugin.
- Blender 4.x.

Verificación del driver:

```bash
nvidia-smi
```

### 1. Instalar CUDA Toolkit

Como base conservadora para esta guía, use **CUDA 12.6** o la rama estable 12.x recomendada por Nvidia para su distribución en el momento de la instalación.

Pasos típicos en Ubuntu 24.04:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-6
```

Verificación:

```bash
nvcc --version
nvidia-smi
```

### 2. Instalar `nvidia-container-toolkit`

Esto es imprescindible para exponer la GPU a contenedores Docker.

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Comprobación rápida:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

### 3. Instalar Ollama con detección automática de CUDA

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

Modelos a descargar:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
ollama pull qwen2.5vl:7b
ollama pull moondream
```

### 4. Ajustes recomendables según VRAM disponible

Sugerencias, no requisitos:

- **12+ GB VRAM**: considerar `qwen2.5:14b` en cuantización `Q5_K_M` en lugar de `Q4_K_M`.
- **16+ GB VRAM**: cargar simultáneamente el modelo de chat y el de embeddings con mucha menos presión de offloading.
- **24+ GB VRAM**: evaluar `qwen2.5:32b` para razonamiento crítico del agente normativo.

### 5. Dependencias Python, frontend y Docker

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l

cd backend
uv sync --all-extras

cd ../frontend
npm install
```

### 6. Ajustes recomendados en `docker-compose.yml`

En Nvidia no debe usarse la estrategia AMD basada en `/dev/kfd` y `/dev/dri`. La reserva recomendada es mediante dispositivos Nvidia en Compose. Ejemplo:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Use este patrón en servicios que necesiten GPU real, especialmente si containeriza Ollama o introduce inferencia de render dentro de contenedores.

### 7. Primera ejecución y verificación

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py

cd ../frontend
npm run build

nvidia-smi
ollama list
```

Si además desea validar Docker con GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

### 8. Troubleshooting Nvidia

#### Error de driver

- Confirme que `nvidia-smi` funciona fuera de Docker antes de depurar Compose.
- Si no funciona, el problema está en el driver, no en Cimiento.

#### `CUDA version mismatch`

- Verifique alineación entre driver, toolkit y contenedor base.
- Priorice el driver del host; el contenedor no corrige un host mal configurado.

#### OOM con modelos grandes

- Baje a cuantización `Q4_K_M`.
- Reduzca número de modelos residentes a la vez.
- Use modelos 7B para validar el sistema antes de subir a 14B o 32B.

#### Docker no ve la GPU

- Revise `nvidia-container-toolkit` y reinicio de Docker.
- Valide primero con `docker run --rm --gpus all ... nvidia-smi`.

---

## Deutsch

### Voraussetzungen

- Linux x86_64, bevorzugt Ubuntu 24.04 LTS.
- Proprietaerer Nvidia-Treiber.
- Konservative Empfehlung: **Treiberzweig 550 oder neuer**.
- Dedizierte Nvidia-GPU mit ausreichend VRAM.
- Docker Engine + Docker Compose Plugin.
- Blender 4.x.

Treiberpruefung:

```bash
nvidia-smi
```

### 1. CUDA Toolkit installieren

Als konservative Basis fuer diese Anleitung wird **CUDA 12.6** oder die jeweils aktuelle stabile 12.x-Linie empfohlen, die Nvidia fuer Ihre Distribution freigibt.

Typische Schritte unter Ubuntu 24.04:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-6
```

Verifikation:

```bash
nvcc --version
nvidia-smi
```

### 2. `nvidia-container-toolkit` installieren

Dies ist notwendig, damit Docker-Container die GPU nutzen koennen.

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Schnelltest:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

### 3. Ollama mit automatischer CUDA-Erkennung installieren

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

Zu ladende Modelle:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull nomic-embed-text
ollama pull qwen2.5vl:7b
ollama pull moondream
```

### 4. Empfohlene Anpassungen je nach verfuegbarem VRAM

Hinweise, keine Pflicht:

- **12+ GB VRAM**: `qwen2.5:14b` in `Q5_K_M` statt `Q4_K_M` pruefen.
- **16+ GB VRAM**: Chat- und Embedding-Modell meist parallel ohne massives Offloading betreiben.
- **24+ GB VRAM**: `qwen2.5:32b` fuer kritisches Reasoning des Norm-Agenten evaluieren.

### 5. Python-Abhaengigkeiten, Frontend und Docker

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL -l

cd backend
uv sync --all-extras

cd ../frontend
npm install
```

### 6. Empfohlene Anpassung in `docker-compose.yml`

Auf Nvidia darf nicht das AMD-Muster mit `/dev/kfd` und `/dev/dri` verwendet werden. Empfohlen ist folgende Compose-Reservierung:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Dieses Muster sollte fuer alle Container verwendet werden, die echte GPU-Beschleunigung benoetigen, insbesondere bei containerisiertem Ollama oder GPU-gestuetzter Render-Inferenz.

### 7. Erster Start und Verifikation

```bash
cd backend
uv run pytest tests/integration/test_api_endpoints.py

cd ../frontend
npm run build

nvidia-smi
ollama list
```

Fuer Docker-GPU-Pruefung zusaetzlich:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```

### 8. Typische Nvidia-Probleme

#### Treiberfehler

- Zuerst pruefen, ob `nvidia-smi` ausserhalb von Docker funktioniert.
- Falls nicht, liegt das Problem im Host-Treiber, nicht in Cimiento.

#### `CUDA version mismatch`

- Treiber, Toolkit und Containerbasis aufeinander abstimmen.
- Der Host-Treiber hat Prioritaet; ein Container heilt keinen falsch installierten Host.

#### OOM bei grossen Modellen

- Auf `Q4_K_M` zurueckgehen.
- Anzahl gleichzeitig geladener Modelle reduzieren.
- Erst mit 7B validieren, dann auf 14B oder 32B skalieren.

#### Docker sieht die GPU nicht

- `nvidia-container-toolkit` und Docker-Neustart kontrollieren.
- Immer zuerst mit `docker run --rm --gpus all ... nvidia-smi` testen.
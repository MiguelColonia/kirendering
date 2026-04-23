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

### 2.b Actualizar ROCm para Blender 5.1 HIP

Si ya tiene ROCm 5.x y `uv run python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official` devuelve que Blender 5.1 no expone HIP, la causa más probable es que Cycles necesita **ROCm HIP Runtime 6.0 o superior**. La ruta oficial actual de AMD para Ubuntu 24.04 publica **ROCm 7.2.2**, que también cubre ese mínimo.

Actualización recomendada en Ubuntu 24.04:

```bash
sudo mkdir --parents --mode=0755 /etc/apt/keyrings
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
	gpg --dearmor | sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null

sudo tee /etc/apt/sources.list.d/rocm.list << 'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/7.2.2 noble main
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/graphics/7.2.1/ubuntu noble main
EOF

sudo tee /etc/apt/preferences.d/rocm-pin-600 << 'EOF'
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
EOF

sudo apt update
sudo apt install python3-setuptools python3-wheel
sudo usermod -a -G render,video $LOGNAME
```

En este proyecto no conviene saltar directamente a `sudo apt install rocm` si ya tiene paquetes ROCm 5.x desde Ubuntu `universe`, porque el conflicto típico es exactamente este:

- `rocminfo` queda fijado en `5.7.1-3build1`.
- el meta-paquete `rocm` de AMD exige `rocminfo = 1.0.0.70202-86~24.04`.
- `amdgpu-dkms` puede no tener candidato si solo ha registrado los repos `rocm` y `graphics`.

Para el caso validado en este host, use esta vía mínima y consistente para Blender 5.1 + HIP:

```bash
sudo apt install --allow-downgrades \
	rocminfo=1.0.0.70202-86~24.04 \
	rocm-hip-runtime \
	hip-runtime-amd
```

Notas prácticas:

- Si `amdgpu-dkms` no tiene candidato, no bloquee aquí la actualización del runtime HIP. Mantenga el driver `amdgpu` del kernel de Ubuntu y siga con la ruta mínima anterior.
- `rocm-hip-runtime` ya arrastra `rocm-core`, `rocm-language-runtime`, `hip-runtime-amd`, `hsa-rocr`, `comgr` y las librerías que Blender necesita para HIP.
- Si más adelante necesita el stack ROCm completo para desarrollo, puede ampliar desde esta base, pero para resolver `compute_device_type: []` en Blender no hace falta empezar por el meta-paquete `rocm`.

Mantenga además el override de RX 6600 si sigue siendo necesario en su host:

```bash
grep -q 'HSA_OVERRIDE_GFX_VERSION=10.3.0' ~/.bashrc || \
	echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.bashrc
source ~/.bashrc
```

Después de la instalación, **reinicie la máquina** antes de validar Blender, Ollama o PyTorch.

Secuencia de verificación posterior:

```bash
rocminfo | grep -i gfx

cd backend
/home/miguel/cimiento/backend/.venv/bin/python - << 'PY'
import torch
print({'torch': torch.__version__, 'hip': torch.version.hip, 'cuda_available': torch.cuda.is_available()})
PY

/home/miguel/cimiento/backend/.venv/bin/python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official
/home/miguel/cimiento/backend/.venv/bin/python scripts/test_render_manual.py --samples 1 --device AUTO --blender /usr/local/bin/blender-official

curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b-instruct-q4_K_M","prompt":"Hallo","stream":false,"keep_alive":"5m"}' >/dev/null
curl -s http://localhost:11434/api/ps
```

Resultado esperado tras la actualización:

- `torch.version.hip` presente y `torch.cuda.is_available() == True`.
- `check_blender_gpu.py` mostrando `HIP` en vez de `compute_device_type: []`.
- `test_render_manual.py` usando `Dispositivo: HIP` o, como mínimo, exponiendo ya el backend HIP en Cycles.
- `/api/ps` de Ollama con `size_vram > 0` cuando haya un modelo cargado.

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

### 3.b Instalar Blender oficial con HIP para Cycles

Si `uv run python scripts/check_blender_gpu.py` indica que la build de Ubuntu no expone backends GPU en Cycles, cambie a la build oficial actual de Blender:

```bash
cd /tmp
wget https://download.blender.org/release/Blender5.1/blender-5.1.1-linux-x64.tar.xz
sudo mkdir -p /opt/blender
sudo tar -xJf blender-5.1.1-linux-x64.tar.xz -C /opt/blender
sudo ln -sfn /opt/blender/blender-5.1.1-linux-x64 /opt/blender/current
sudo ln -sfn /opt/blender/current/blender /usr/local/bin/blender-official
```

Después, apunte Cimiento a esa build:

```bash
cd backend
cp -n .env.example .env
grep -q '^BLENDER_EXECUTABLE=' .env || printf '\nBLENDER_EXECUTABLE=/usr/local/bin/blender-official\n' >> .env
uv run python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official
uv run python scripts/test_render_manual.py --samples 1 --device AUTO
```

Si el diagnóstico muestra `HIP` y el render manual ya no cae a CPU, el backend API usará esa ruta automáticamente vía `BLENDER_EXECUTABLE`.

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
- Si `blender --background --python-expr ...` muestra `compute_device_type` vacío o `NONE`, la build de Blender no expone HIP aunque ROCm funcione para PyTorch u Ollama.
- En Ubuntu 24.04 esto puede ocurrir con el paquete `blender 4.0.2+dfsg-1ubuntu8` de `universe`.
- Para Blender oficial 5.1 en Linux, Cycles exige al menos `ROCm HIP Runtime 6.0`. Con `libamdhip64 5.7.1` el síntoma observado es `WARNING Driver version is too old` y `compute_device_type: []`.
- Use `cd backend && uv run python scripts/check_blender_gpu.py` para diagnosticarlo.
- Si el host sigue en ROCm 5.x, aplique primero la actualización de la sección `2.b` antes de seguir depurando Blender.
- Si confirma ese caso, instale la build oficial de Blender 5.1.1 indicada arriba y configure `BLENDER_EXECUTABLE=/usr/local/bin/blender-official`.
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

### 2.b ROCm fuer Blender 5.1 HIP aktualisieren

Wenn bereits ROCm 5.x installiert ist und `uv run python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official` meldet, dass Blender 5.1 kein HIP exponiert, ist die wahrscheinlichste Ursache die Mindestanforderung von Cycles: **ROCm HIP Runtime 6.0 oder neuer**. Der aktuelle offizielle AMD-Weg fuer Ubuntu 24.04 liefert **ROCm 7.2.2** und erfuellt diese Bedingung.

Empfohlene Aktualisierung unter Ubuntu 24.04:

```bash
sudo mkdir --parents --mode=0755 /etc/apt/keyrings
wget https://repo.radeon.com/rocm/rocm.gpg.key -O - | \
	gpg --dearmor | sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null

sudo tee /etc/apt/sources.list.d/rocm.list << 'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/7.2.2 noble main
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/graphics/7.2.1/ubuntu noble main
EOF

sudo tee /etc/apt/preferences.d/rocm-pin-600 << 'EOF'
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
EOF

sudo apt update
sudo apt install python3-setuptools python3-wheel
sudo usermod -a -G render,video $LOGNAME
```

In diesem Projekt sollte man **nicht** direkt `sudo apt install rocm` ausfuehren, wenn bereits ROCm-5.x-Pakete aus Ubuntu `universe` installiert sind, weil genau dann typischerweise dieser Konflikt entsteht:

- `rocminfo` bleibt auf `5.7.1-3build1`.
- das AMD-Metapaket `rocm` verlangt `rocminfo = 1.0.0.70202-86~24.04`.
- `amdgpu-dkms` kann ohne zusaetzlich registriertes AMDGPU-Repo ganz fehlen.

Fuer den hier verifizierten Fall ist dieser minimale und konsistente Weg fuer Blender 5.1 + HIP vorzuziehen:

```bash
sudo apt install --allow-downgrades \
	rocminfo=1.0.0.70202-86~24.04 \
	rocm-hip-runtime \
	hip-runtime-amd
```

Praktische Hinweise:

- Wenn `amdgpu-dkms` keinen Installationskandidaten hat, die Runtime-Aktualisierung nicht daran scheitern lassen. Den Ubuntu-Kernel-Treiber `amdgpu` beibehalten und mit dem minimalen HIP-Runtime-Pfad weitermachen.
- `rocm-hip-runtime` zieht bereits `rocm-core`, `rocm-language-runtime`, `hip-runtime-amd`, `hsa-rocr`, `comgr` und die fuer Blender relevanten Bibliotheken nach.
- Falls spaeter der komplette ROCm-Entwicklungsstack benoetigt wird, kann darauf aufgebaut werden. Fuer das konkrete Blender-Problem `compute_device_type: []` ist das aber nicht der erste Schritt.

Den RX-6600-Override bei Bedarf beibehalten:

```bash
grep -q 'HSA_OVERRIDE_GFX_VERSION=10.3.0' ~/.bashrc || \
	echo 'export HSA_OVERRIDE_GFX_VERSION=10.3.0' >> ~/.bashrc
source ~/.bashrc
```

Nach der Installation den Rechner **neu starten**, bevor Blender, Ollama oder PyTorch getestet werden.

Verifikationsfolge danach:

```bash
rocminfo | grep -i gfx

cd backend
/home/miguel/cimiento/backend/.venv/bin/python - << 'PY'
import torch
print({'torch': torch.__version__, 'hip': torch.version.hip, 'cuda_available': torch.cuda.is_available()})
PY

/home/miguel/cimiento/backend/.venv/bin/python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official
/home/miguel/cimiento/backend/.venv/bin/python scripts/test_render_manual.py --samples 1 --device AUTO --blender /usr/local/bin/blender-official

curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b-instruct-q4_K_M","prompt":"Hallo","stream":false,"keep_alive":"5m"}' >/dev/null
curl -s http://localhost:11434/api/ps
```

Erwartetes Ergebnis nach der Aktualisierung:

- `torch.version.hip` ist gesetzt und `torch.cuda.is_available() == True`.
- `check_blender_gpu.py` zeigt `HIP` statt `compute_device_type: []`.
- `test_render_manual.py` nutzt `Dispositivo: HIP` oder zeigt zumindest den HIP-Backend in Cycles.
- In Ollama zeigt `/api/ps` bei geladenem Modell `size_vram > 0`.

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

### 3.b Offizielles Blender mit HIP fuer Cycles installieren

Wenn `uv run python scripts/check_blender_gpu.py` meldet, dass die Ubuntu-Build keine GPU-Backends in Cycles anbietet, auf die aktuelle offizielle Blender-Build wechseln:

```bash
cd /tmp
wget https://download.blender.org/release/Blender5.1/blender-5.1.1-linux-x64.tar.xz
sudo mkdir -p /opt/blender
sudo tar -xJf blender-5.1.1-linux-x64.tar.xz -C /opt/blender
sudo ln -sfn /opt/blender/blender-5.1.1-linux-x64 /opt/blender/current
sudo ln -sfn /opt/blender/current/blender /usr/local/bin/blender-official
```

Danach Cimiento auf diese Build umstellen:

```bash
cd backend
cp -n .env.example .env
grep -q '^BLENDER_EXECUTABLE=' .env || printf '\nBLENDER_EXECUTABLE=/usr/local/bin/blender-official\n' >> .env
uv run python scripts/check_blender_gpu.py --blender /usr/local/bin/blender-official
uv run python scripts/test_render_manual.py --samples 1 --device AUTO
```

Wenn der Diagnose-Output danach `HIP` zeigt und der manuelle Render nicht mehr auf CPU faellt, nutzt die API diese Blender-Route automatisch ueber `BLENDER_EXECUTABLE`.

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
- Wenn `blender --background --python-expr ...` bei `compute_device_type` nur `[]` oder `NONE` liefert, stellt diese Blender-Build kein HIP fuer Cycles bereit, auch wenn ROCm fuer PyTorch oder Ollama funktioniert.
- Unter Ubuntu 24.04 kann das beim Paket `blender 4.0.2+dfsg-1ubuntu8` aus `universe` auftreten.
- Fuer offizielles Blender 5.1 unter Linux benoetigt Cycles mindestens `ROCm HIP Runtime 6.0`. Mit `libamdhip64 5.7.1` zeigt Cycles typischerweise `WARNING Driver version is too old` und `compute_device_type: []`.
- Zur Diagnose: `cd backend && uv run python scripts/check_blender_gpu.py`
- Wenn der Host noch auf ROCm 5.x steht, zuerst Abschnitt `2.b` anwenden, bevor weiter an Blender debuggt wird.
- In diesem Fall die oben gezeigte offizielle Blender-5.1.1-Build installieren und `BLENDER_EXECUTABLE=/usr/local/bin/blender-official` setzen.
- Wenn ROCm nicht stabil ist, CPU/Vulkan-Fallback bewusst akzeptieren.

#### Docker erreicht Ollama auf dem Host nicht

- In Produktion `host.docker.internal` plus `extra_hosts` verwenden.
- Fuer lokale Tests Ollama zunaechst direkt auf dem Host betreiben.
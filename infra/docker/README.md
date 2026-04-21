# Docker en desarrollo y producción / Docker fuer Entwicklung und Produktion

## Español

### Diferencias entre `docker-compose.yml` y `docker-compose.prod.yml`

`docker-compose.yml` se mantiene como stack de desarrollo:

- expone frontend, backend y base de datos al host,
- simplifica el arranque local,
- admite el perfil opcional `ai` para Ollama y Qdrant.

`docker-compose.prod.yml` queda orientado a despliegue persistente:

- **PostgreSQL y Qdrant no exponen puertos al host**;
- variables desde `.env.prod`;
- healthchecks en todos los servicios;
- política `restart: unless-stopped`;
- volúmenes nombrados con prefijo `cimiento_prod_`;
- backend desde Dockerfile multi-stage;
- frontend servido por Nginx, que además hace proxy de `/api` hacia el backend;
- Ollama opcional: host o contenedor según `OLLAMA_HOST` y `--profile ollama`.

### Arranque de desarrollo

Stack base:

```bash
cd infra/docker
docker compose up --build -d
```

Con servicios IA opcionales:

```bash
cd infra/docker
docker compose --profile ai up -d
```

### Arranque de producción

1. Copiar el archivo de ejemplo:

```bash
cd infra/docker
cp .env.prod.example .env.prod
```

2. Editar secretos, `DATABASE_URL` y el modo de Ollama.

3. Si Ollama va en el host, dejar por defecto:

```env
OLLAMA_HOST=http://host.docker.internal:11434
```

4. Si Ollama va en contenedor, cambiar a:

```env
OLLAMA_HOST=http://ollama:11434
```

y arrancar con perfil:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ollama up -d
```

Si usa Ollama del host:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

### Notas operativas

- El frontend es el punto de entrada HTTP y hace de reverse proxy para `/api`.
- El backend depende de PostgreSQL y Qdrant; Ollama puede estar en host o contenedor.
- Para GPU Nvidia en contenedores, sustituir el patrón AMD por reservas `driver: nvidia` en los servicios que realmente necesiten GPU.
- No se han construido imágenes en este cierre; la verificación de producción debe hacerse en la máquina de destino.

## Deutsch

### Unterschiede zwischen `docker-compose.yml` und `docker-compose.prod.yml`

`docker-compose.yml` bleibt der Entwicklungs-Stack:

- Frontend, Backend und Datenbank werden zum Host durchgereicht,
- der lokale Start ist moeglichst direkt,
- ueber das Profil `ai` lassen sich Ollama und Qdrant zusaetzlich starten.

`docker-compose.prod.yml` ist fuer den dauerhaften Betrieb gedacht:

- **PostgreSQL und Qdrant oeffnen keine Ports zum Host**;
- Variablen kommen aus `.env.prod`;
- alle Services besitzen Healthchecks;
- `restart: unless-stopped` ist gesetzt;
- benannte Volumes tragen das Praefix `cimiento_prod_`;
- das Backend wird aus einem Multi-Stage-Dockerfile gebaut;
- das Frontend laeuft hinter Nginx, das zugleich `/api` zum Backend proxyt;
- Ollama ist optional: Host-Betrieb oder Container ueber `OLLAMA_HOST` und `--profile ollama`.

### Entwicklungsstart

Basis-Stack:

```bash
cd infra/docker
docker compose up --build -d
```

Mit optionalen KI-Diensten:

```bash
cd infra/docker
docker compose --profile ai up -d
```

### Produktionsstart

1. Beispieldatei kopieren:

```bash
cd infra/docker
cp .env.prod.example .env.prod
```

2. Secrets, `DATABASE_URL` und den Ollama-Modus anpassen.

3. Fuer Host-Ollama den Standard belassen:

```env
OLLAMA_HOST=http://host.docker.internal:11434
```

4. Fuer containerisiertes Ollama auf

```env
OLLAMA_HOST=http://ollama:11434
```

umstellen und mit Profil starten:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ollama up -d
```

Fuer Host-Ollama:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

### Betriebsnotizen

- Das Frontend ist der HTTP-Einstiegspunkt und uebernimmt zugleich das Reverse Proxying fuer `/api`.
- Das Backend haengt an PostgreSQL und Qdrant; Ollama kann auf dem Host oder im Container laufen.
- Fuer Nvidia-GPUs muessen in Compose Reservierungen mit `driver: nvidia` genutzt werden, nicht das AMD-Muster mit `/dev/kfd` und `/dev/dri`.
- In diesem Abschluss wurden keine Produktionsimages gebaut; die Endpruefung muss auf der Zielmaschine erfolgen.
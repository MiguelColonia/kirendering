FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend /build/backend

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip wheel --no-cache-dir --wheel-dir /tmp/wheels .

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends blender ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /tmp/wheels /tmp/wheels

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /tmp/wheels/* \
    && rm -rf /tmp/wheels

COPY backend /app/backend

EXPOSE 8000

CMD ["uvicorn", "cimiento.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""Configuración central de Cimiento."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Cimiento"
    debug: bool = False

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model_reasoning: str = "qwen2.5:14b-instruct-q4_K_M"
    ollama_model_fast: str = "qwen2.5:7b-instruct-q4_K_M"
    ollama_model_chat: str = "qwen2.5:7b-instruct-q4_K_M"
    ollama_model_coder: str = "qwen2.5-coder:7b-instruct-q4_K_M"
    ollama_model_embed: str = "nomic-embed-text"
    ollama_model_vision: str = "qwen2.5vl:7b"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "normativa"

    # Base de datos
    database_url: str = "postgresql+asyncpg://cimiento:cimiento@localhost:5432/cimiento"

    # Solver
    solver_timeout_seconds: int = 60

    # Render
    blender_executable: str = "blender"
    render_samples: int = 64
    render_width: int = 2048
    render_height: int = 1152
    render_timeout_seconds: int = 600


settings = Settings()

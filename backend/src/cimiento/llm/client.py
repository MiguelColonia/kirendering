"""Cliente async para Ollama con resolución de modelos por rol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypeAlias

import httpx
from pydantic import BaseModel, ConfigDict, Field

from cimiento.core.config import Settings
from cimiento.core.config import settings as default_settings

MessageRole = Literal["system", "user", "assistant", "tool"]
ModelRole = Literal[
    "planner",
    "validator",
    "normative",
    "extractor",
    "requirements",
    "simple",
    "chat",
    "coder",
]


class OllamaChatMessage(BaseModel):
    """Mensaje compatible con el endpoint `/api/chat` de Ollama."""

    model_config = ConfigDict(extra="allow")

    role: MessageRole
    content: str
    images: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None


class JsonSchemaDefinition(BaseModel):
    """Definición OpenAI-like para `response_format=json_schema`."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str
    description: str | None = None
    strict: bool | None = None
    json_schema: dict[str, Any] = Field(alias="schema")


class JsonSchemaResponseFormat(BaseModel):
    """Wrapper compatible con `response_format={type: json_schema, ...}`."""

    model_config = ConfigDict(extra="allow")

    type: Literal["json_schema"]
    json_schema: JsonSchemaDefinition


class OllamaChatResponse(BaseModel):
    """Respuesta normalizada del endpoint de chat de Ollama."""

    model_config = ConfigDict(extra="allow")

    model: str
    created_at: str | None = None
    message: OllamaChatMessage
    done: bool
    done_reason: str | None = None
    total_duration: int | None = None
    load_duration: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration: int | None = None
    eval_count: int | None = None
    eval_duration: int | None = None

    @property
    def content(self) -> str:
        """Devuelve el contenido textual del mensaje asistente."""
        return self.message.content


MessageInput: TypeAlias = OllamaChatMessage | Mapping[str, Any]
ResponseFormatInput: TypeAlias = str | JsonSchemaResponseFormat | Mapping[str, Any]
ToolInput: TypeAlias = Mapping[str, Any]


def _normalize_messages(messages: Sequence[MessageInput]) -> list[OllamaChatMessage]:
    if not messages:
        raise ValueError("Se requiere al menos un mensaje para invocar Ollama.")

    return [
        message
        if isinstance(message, OllamaChatMessage)
        else OllamaChatMessage.model_validate(message)
        for message in messages
    ]


def _normalize_response_format(
    response_format: ResponseFormatInput | None,
) -> str | dict[str, Any] | None:
    if response_format is None:
        return None

    if isinstance(response_format, str):
        return response_format

    if isinstance(response_format, JsonSchemaResponseFormat):
        return response_format.json_schema.json_schema

    format_dict = dict(response_format)
    if format_dict.get("type") == "json_schema":
        json_schema = format_dict.get("json_schema")
        if not isinstance(json_schema, Mapping):
            raise ValueError("`json_schema` debe ser un mapping con una clave `schema`.")

        schema = json_schema.get("schema")
        if not isinstance(schema, Mapping):
            raise ValueError("`json_schema.schema` debe ser un objeto JSON Schema válido.")
        return dict(schema)

    return format_dict


class OllamaClient:
    """Wrapper async sobre la API HTTP de Ollama."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or default_settings
        self._base_url = (base_url or self._settings.ollama_host).rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        """Devuelve la URL base configurada para Ollama."""
        return self._base_url

    def model_for_role(self, role: ModelRole) -> str:
        """Resuelve el modelo adecuado según el rol lógico del agente."""
        role_mapping: dict[ModelRole, str] = {
            "planner": self._settings.ollama_model_reasoning,
            "validator": self._settings.ollama_model_reasoning,
            "normative": self._settings.ollama_model_reasoning,
            "extractor": self._settings.ollama_model_fast,
            "requirements": self._settings.ollama_model_fast,
            "simple": self._settings.ollama_model_fast,
            "chat": self._settings.ollama_model_chat,
            "coder": self._settings.ollama_model_coder,
        }
        try:
            return role_mapping[role]
        except KeyError as exc:
            valid_roles = ", ".join(sorted(role_mapping))
            raise ValueError(
                f"Rol LLM no soportado: {role}. Roles válidos: {valid_roles}."
            ) from exc

    async def chat(
        self,
        messages: Sequence[MessageInput],
        role: ModelRole,
        format: ResponseFormatInput | None = None,
        tools: Sequence[ToolInput] | None = None,
    ) -> OllamaChatResponse:
        """Envía una conversación a Ollama y devuelve la respuesta final no streaming."""
        normalized_messages = _normalize_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model_for_role(role),
            "messages": [message.model_dump(exclude_none=True) for message in normalized_messages],
            "stream": False,
        }

        normalized_format = _normalize_response_format(format)
        if normalized_format is not None:
            payload["format"] = normalized_format

        if tools is not None:
            payload["tools"] = [dict(tool) for tool in tools]

        response = await self._get_client().post("/api/chat", json=payload)
        response.raise_for_status()
        return OllamaChatResponse.model_validate(response.json())

    async def aclose(self) -> None:
        """Cierra el cliente HTTP subyacente si fue inicializado."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OllamaClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            )
        return self._client

"""
Endpoints de chat conversacional para el copiloto de Cimiento.

POST   /api/projects/{project_id}/chat          — respuesta completa (non-streaming)
WS     /api/projects/{project_id}/chat/stream   — progreso nodo a nodo + respuesta final

Protocolo WebSocket (servidor → cliente):
  {"type": "node_start",  "node": "<nombre>", "label": "<texto alemán>"}
  {"type": "node_end",    "node": "<nombre>"}
  {"type": "done",        "response": "<texto>", "solution": {...} | null, "feasible": bool}
  {"type": "error",       "message": "<texto>"}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from cimiento.api.dependencies import get_repository
from cimiento.api.errors import project_not_found
from cimiento.persistence.repository import ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Etiquetas alemanas que se envían al cliente para cada nodo del grafo
_NODE_LABELS: dict[str, str] = {
    "extract_requirements": "Anforderungen werden analysiert\u2026",
    "validate_normative": "Normvorschriften werden geprüft\u2026",
    "invoke_solver": "Solver läuft\u2026",
    "interpret_result": "Antwort wird generiert\u2026",
    "handle_infeasible": "Anpassungsvorschläge werden erstellt\u2026",
}

_GRAPH_NODES = set(_NODE_LABELS.keys())


# ---------------------------------------------------------------------------
# Schemas de entrada / salida HTTP
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Cuerpo de la petición POST /chat."""

    message: str = Field(..., min_length=1, max_length=4096)
    thread_id: str | None = Field(
        default=None,
        description=(
            "Identificador de hilo para conversación multi-turno. "
            "Si es null se usa '{project_id}-chat'."
        ),
    )


class ChatResponse(BaseModel):
    """Respuesta del endpoint POST /chat."""

    response: str
    thread_id: str
    feasible: bool
    solution: dict | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _thread_id(project_id: str, override: str | None) -> str:
    return override or f"{project_id}-chat"


def _extract_final_state(state: dict) -> tuple[str, bool, dict | None]:
    """
    Extrae response, feasible y solution del estado final del grafo.

    Devuelve (response_de, feasible, solution_dict).
    """
    response = state.get("user_response_de") or ""
    solution = state.get("solution")
    feasible = True
    if solution:
        feasible = solution.get("status") in ("OPTIMAL", "FEASIBLE")
    return response, feasible, solution


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/chat
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    project_id: str,
    body: ChatRequest,
    request: Request,
    repository: ProjectRepository = Depends(get_repository),
) -> ChatResponse:
    """
    Invoca el grafo de agentes con el mensaje del usuario y devuelve la respuesta completa.

    Usa el mismo thread_id para toda la sesión de chat de un proyecto, lo que permite
    conversación multi-turno con MemorySaver.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise project_not_found(project_id)

    graph = request.app.state.chat_graph
    tid = _thread_id(project_id, body.thread_id)

    state = await graph.ainvoke(
        {"user_message": body.message},
        config={"configurable": {"thread_id": tid}},
    )

    response, feasible, solution = _extract_final_state(state)
    return ChatResponse(
        response=response,
        thread_id=tid,
        feasible=feasible,
        solution=solution,
    )


# ---------------------------------------------------------------------------
# WebSocket /api/projects/{project_id}/chat/stream
# ---------------------------------------------------------------------------


@router.websocket("/projects/{project_id}/chat/stream")
async def chat_stream(
    websocket: WebSocket,
    project_id: str,
) -> None:
    """
    Streaming de la ejecución del grafo: envía un evento por cada nodo que se activa
    y la respuesta final cuando el grafo completa.

    El cliente debe enviar un primer mensaje JSON: {"message": "...", "thread_id": "..."}
    """
    repository = ProjectRepository(websocket.app.state.session_factory)
    await websocket.accept()

    project = await repository.get_project(project_id)
    if project is None:
        await websocket.send_json({"type": "error", "message": "Projekt nicht gefunden."})
        await websocket.close(code=4404)
        return

    try:
        raw = await websocket.receive_json()
    except WebSocketDisconnect:
        return

    message: str = raw.get("message", "").strip()
    if not message:
        await websocket.send_json({"type": "error", "message": "Leere Nachricht."})
        await websocket.close()
        return

    tid = _thread_id(project_id, raw.get("thread_id"))
    graph = websocket.app.state.chat_graph

    try:
        final_state: dict = {}
        async for event in graph.astream_events(
            {"user_message": message},
            config={"configurable": {"thread_id": tid}},
            version="v2",
        ):
            event_name: str = event.get("name", "")
            event_type: str = event.get("event", "")

            if event_type == "on_chain_start" and event_name in _GRAPH_NODES:
                await websocket.send_json({
                    "type": "node_start",
                    "node": event_name,
                    "label": _NODE_LABELS[event_name],
                })

            elif event_type == "on_chain_end" and event_name in _GRAPH_NODES:
                await websocket.send_json({
                    "type": "node_end",
                    "node": event_name,
                })
                # Capturar el estado de salida del último nodo para la respuesta final
                output = event.get("data", {}).get("output") or {}
                if isinstance(output, dict):
                    final_state.update(output)

        response, feasible, solution = _extract_final_state(final_state)
        await websocket.send_json({
            "type": "done",
            "response": response,
            "feasible": feasible,
            "solution": solution,
        })
        await websocket.close()

    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado del chat del proyecto '%s'", project_id)
    except Exception:
        logger.exception("Error en chat stream del proyecto '%s'", project_id)
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Interner Fehler bei der Verarbeitung der Anfrage.",
            })
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass

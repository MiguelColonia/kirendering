"""
Router de chat conversacional del copiloto de Cimiento.

Expone un único endpoint WebSocket:
  WS /api/projects/{project_id}/chat/stream

El cliente envía un primer JSON: {"message": "...", "thread_id": "..."}
El servidor ejecuta el grafo LangGraph (design_assistant) en modo streaming
y emite un evento por cada nodo que se activa, seguido de la respuesta final.

Protocolo WebSocket (servidor → cliente):
  {"type": "node_start",  "node": "<nombre>", "label": "<texto alemán>"}
  {"type": "node_end",    "node": "<nombre>"}
  {"type": "done",        "response": "<texto>", "solution": {...} | null, "feasible": bool}
  {"type": "error",       "message": "<texto>"}

El thread_id permite persistencia multi-turno vía el MemorySaver del grafo.
Si no se provee, se genera uno automático basado en el project_id.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
                await websocket.send_json(
                    {
                        "type": "node_start",
                        "node": event_name,
                        "label": _NODE_LABELS[event_name],
                    }
                )

            elif event_type == "on_chain_end" and event_name in _GRAPH_NODES:
                await websocket.send_json(
                    {
                        "type": "node_end",
                        "node": event_name,
                    }
                )
                # Capturar el estado de salida del último nodo para la respuesta final
                output = event.get("data", {}).get("output") or {}
                if isinstance(output, dict):
                    final_state.update(output)

        response, feasible, solution = _extract_final_state(final_state)
        await websocket.send_json(
            {
                "type": "done",
                "response": response,
                "feasible": feasible,
                "solution": solution,
            }
        )
        await websocket.close()

    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado del chat del proyecto '%s'", project_id)
    except Exception:
        logger.exception("Error en chat stream del proyecto '%s'", project_id)
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Interner Fehler bei der Verarbeitung der Anfrage.",
                }
            )
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass

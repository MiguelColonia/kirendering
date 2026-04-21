"""
Benchmark de latencia del chat del copiloto Cimiento.

Mide el tiempo medio por turno de conversación contra el endpoint WebSocket
/api/projects/{project_id}/chat/stream con distintos modelos configurables
mediante variables de entorno de Ollama.

Uso:
    python benchmark_chat.py --host http://localhost:8000 --project-id <ID>

Requisitos:
    - Backend Cimiento activo con un proyecto existente.
    - pip install websockets httpx

El script:
1. Envía N prompts de referencia vía WebSocket.
2. Mide el tiempo desde la apertura de la conexión hasta recibir el evento "done".
3. Registra el nodo que más tiempo consumió por turno.
4. Imprime un resumen estadístico (media, p50, p90, p95).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field

import websockets

PROMPTS = [
    "Ich habe ein Grundstück von 20x30 Metern und möchte 10 Wohnungen mit zwei Schlafzimmern planen.",
    "Grundstück 15x25 m, 3 Geschosse, 6 Dreizimmerwohnungen.",
    "Solar 40x50 Meter, 5 Etagen, 20 Einheiten T2 und 10 Einheiten T3.",
    "Grundstück 10x20 m, Erdgeschoss, 4 kleine Wohnungen mit 1 Schlafzimmer.",
    "50x60 Meter Grundstück, 8 Stockwerke, 40 Zweizimmerwohnungen.",
]


@dataclass
class TurnResult:
    prompt: str
    total_seconds: float
    feasible: bool
    nodes_seen: list[str] = field(default_factory=list)
    error: str | None = None


async def run_turn(ws_url: str, prompt: str, thread_id: str) -> TurnResult:
    nodes: list[str] = []
    t0 = time.perf_counter()
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            await ws.send(json.dumps({"message": prompt, "thread_id": thread_id}))
            async for raw in ws:
                event = json.loads(raw)
                etype = event.get("type")
                if etype == "node_start":
                    nodes.append(event.get("node", "?"))
                elif etype == "done":
                    elapsed = time.perf_counter() - t0
                    return TurnResult(
                        prompt=prompt[:60],
                        total_seconds=elapsed,
                        feasible=event.get("feasible", False),
                        nodes_seen=nodes,
                    )
                elif etype == "error":
                    elapsed = time.perf_counter() - t0
                    return TurnResult(
                        prompt=prompt[:60],
                        total_seconds=elapsed,
                        feasible=False,
                        nodes_seen=nodes,
                        error=event.get("message"),
                    )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return TurnResult(
            prompt=prompt[:60],
            total_seconds=elapsed,
            feasible=False,
            nodes_seen=nodes,
            error=str(exc),
        )
    elapsed = time.perf_counter() - t0
    return TurnResult(prompt=prompt[:60], total_seconds=elapsed, feasible=False, nodes_seen=nodes)


async def main(host: str, project_id: str, repeats: int) -> None:
    ws_host = host.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_host}/api/projects/{project_id}/chat/stream"
    thread_id = f"benchmark-{project_id}"

    results: list[TurnResult] = []
    prompts = (PROMPTS * ((repeats // len(PROMPTS)) + 1))[:repeats]

    print(f"Benchmark Cimiento Chat  —  {len(prompts)} turnos contra {ws_url}\n")

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i:02d}/{len(prompts)}] {prompt[:55]}…", end=" ", flush=True)
        result = await run_turn(ws_url, prompt, thread_id)
        results.append(result)
        if result.error:
            print(f"ERROR ({result.total_seconds:.1f}s): {result.error}")
        else:
            status = "✓ machbar" if result.feasible else "✗ infactible"
            print(f"{result.total_seconds:.1f}s  {status}  nodes={result.nodes_seen}")

    ok = [r for r in results if not r.error]
    if not ok:
        print("\nTodos los turnos fallaron. Verificar que el backend esté activo.")
        return

    times = [r.total_seconds for r in ok]
    feasible_times = [r.total_seconds for r in ok if r.feasible]
    infeasible_times = [r.total_seconds for r in ok if not r.feasible]

    print(f"\n{'─' * 52}")
    print(f"  Turnos válidos   : {len(ok)} / {len(results)}")
    print(f"  Media total      : {statistics.mean(times):.1f} s")
    print(f"  Mediana (p50)    : {statistics.median(times):.1f} s")
    if len(times) >= 5:
        times_sorted = sorted(times)
        p90 = times_sorted[int(len(times_sorted) * 0.9)]
        p95 = times_sorted[int(len(times_sorted) * 0.95)]
        print(f"  p90              : {p90:.1f} s")
        print(f"  p95              : {p95:.1f} s")
    if feasible_times:
        print(f"  Media (factible) : {statistics.mean(feasible_times):.1f} s  ({len(feasible_times)} turnos)")
    if infeasible_times:
        print(f"  Media (infactible): {statistics.mean(infeasible_times):.1f} s  ({len(infeasible_times)} turnos)")
    print(f"{'─' * 52}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark de latencia del chat Cimiento")
    parser.add_argument("--host", default="http://localhost:8000", help="URL base del backend")
    parser.add_argument("--project-id", required=True, help="ID de un proyecto existente")
    parser.add_argument("--repeats", type=int, default=5, help="Número de turnos a ejecutar")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.project_id, args.repeats))

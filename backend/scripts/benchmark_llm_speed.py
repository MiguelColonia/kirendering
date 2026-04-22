"""
Benchmark de velocidad de inferencia para todos los modelos del proyecto.

Mide TPS (tokens/segundo) y latencia por modelo.
Compara CPU baseline contra GPU si está disponible.

Uso:
    cd backend && uv run python scripts/benchmark_llm_speed.py
    cd backend && uv run python scripts/benchmark_llm_speed.py --models 7b coder
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

OLLAMA_BASE = "http://localhost:11434"

MODELS = {
    "7b": "qwen2.5:7b-instruct-q4_K_M",
    "14b": "qwen2.5:14b-instruct-q4_K_M",
    "coder": "qwen2.5-coder:7b-instruct-q4_K_M",
    "embed": "nomic-embed-text",
}

PROMPTS = {
    "short": "Antworte kurz: Was ist ein Flachdach?",
    "medium": (
        "Beschreibe die wichtigsten Anforderungen der MBO 2016 für Wohngebäude "
        "mit mehr als 3 Geschossen in 3-4 Sätzen."
    ),
    "json": (
        "Extrahiere folgende Parameter aus dem Text als JSON:\n"
        "Text: 'Ich möchte ein Grundstück von 25x40 Metern mit 4 Stockwerken und 8 T2-Wohnungen.'\n"
        "Antworte nur mit JSON: {solar_width_m, solar_height_m, num_floors, count}"
    ),
}


async def benchmark_model_async(
    model: str,
    prompt: str,
    prompt_label: str,
    n_runs: int = 2,
) -> dict[str, Any]:
    """Benchmarkea un modelo con el prompt dado."""
    results = []
    async with httpx.AsyncClient(timeout=180.0) as client:
        for run in range(n_runs):
            t0 = time.perf_counter()
            resp = await client.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            elapsed = time.perf_counter() - t0
            data = resp.json()
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 1)
            load_duration_ns = data.get("load_duration", 0)
            tps = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0
            results.append(
                {
                    "run": run + 1,
                    "total_s": elapsed,
                    "load_s": load_duration_ns / 1e9,
                    "gen_s": eval_duration_ns / 1e9,
                    "tokens": eval_count,
                    "tps": tps,
                }
            )

    avg_tps = sum(r["tps"] for r in results) / len(results)
    avg_total = sum(r["total_s"] for r in results) / len(results)
    avg_tokens = sum(r["tokens"] for r in results) / len(results)
    return {
        "model": model,
        "prompt": prompt_label,
        "runs": results,
        "avg_tps": avg_tps,
        "avg_total_s": avg_total,
        "avg_tokens": avg_tokens,
    }


async def check_gpu_status() -> dict[str, Any]:
    """Verifica el estado de la GPU en Ollama."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{OLLAMA_BASE}/api/ps")
        ps = resp.json().get("models", [])
    total_vram = sum(m.get("size_vram", 0) for m in ps)
    return {
        "gpu_active": total_vram > 0,
        "total_vram_gb": total_vram / 1e9,
        "loaded_models": [m["name"] for m in ps],
    }


async def run_benchmarks(model_keys: list[str]) -> None:
    gpu_status = await check_gpu_status()
    mode = "GPU" if gpu_status["gpu_active"] else "CPU"

    print(f"\n{'=' * 65}")
    print(f"  BENCHMARK CIMIENTO — modo: {mode}")
    print(f"  VRAM en uso: {gpu_status['total_vram_gb']:.2f} GB")
    print(f"{'=' * 65}\n")

    all_results = []
    for key in model_keys:
        if key not in MODELS:
            print(f"  Modelo desconocido: {key}, disponibles: {list(MODELS.keys())}")
            continue
        model = MODELS[key]
        print(f"  [{key}] {model}")
        for p_label, p_text in PROMPTS.items():
            print(f"    Prompt: {p_label} ...", end=" ", flush=True)
            result = await benchmark_model_async(model, p_text, p_label, n_runs=2)
            print(
                f"{result['avg_total_s']:.1f}s total | "
                f"{result['avg_tps']:.1f} TPS | "
                f"{result['avg_tokens']:.0f} tokens"
            )
            all_results.append(result)
        print()

    # Guardar resultados
    out_path = Path(__file__).parent.parent / "data" / "outputs" / "benchmark_llm.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"mode": mode, "gpu_status": gpu_status, "results": all_results}, f, indent=2)
    print(f"  Resultados guardados en: {out_path}")
    print(f"\n  RESUMEN ({mode}):")
    for r in all_results:
        print(f"    {r['model'][:30]:30s} [{r['prompt']:6s}] {r['avg_tps']:5.1f} TPS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de velocidad LLM de Cimiento")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODELS.keys()),
        choices=list(MODELS.keys()),
        help="Modelos a benchmarkear",
    )
    args = parser.parse_args()
    asyncio.run(run_benchmarks(args.models))


if __name__ == "__main__":
    main()

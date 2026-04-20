"""Smoke test manual del cliente Ollama de Cimiento.

Uso:
    python scripts/chat_ollama_smoke.py
    python scripts/chat_ollama_smoke.py --prompt "Resume la fase 5 en una frase"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cimiento.llm.client import OllamaClient


async def run(prompt: str) -> None:
    client = OllamaClient()
    try:
        response = await client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "Responde en una sola frase breve y en español.",
                },
                {"role": "user", "content": prompt},
            ],
            role="chat",
        )
    finally:
        await client.aclose()

    print(f"Modelo: {response.model}")
    print(f"Respuesta: {response.content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test manual del cliente Ollama.")
    parser.add_argument(
        "--prompt",
        default="Di hola desde Cimiento en una frase.",
        help="Prompt de prueba enviado a Ollama.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.prompt))


if __name__ == "__main__":
    main()

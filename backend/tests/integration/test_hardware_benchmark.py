"""
Suite de diagnóstico y benchmarking de hardware, GPU, Ollama y agentes.

Ejecutar con:
    cd backend && pytest tests/integration/test_hardware_benchmark.py -v -s

Los tests NO usan mocks — llaman al stack real (Ollama, Qdrant, solver).
Marcar con `@pytest.mark.slow` los tests que toman más de 5 segundos.
"""

from __future__ import annotations

import asyncio
import statistics
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
import pytest

# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

OLLAMA_BASE = "http://localhost:11434"
REQUIRED_MODELS = [
    "qwen2.5:7b-instruct-q4_K_M",
    "qwen2.5:14b-instruct-q4_K_M",
    "qwen2.5-coder:7b-instruct-q4_K_M",
    "nomic-embed-text:latest",
]

# Umbrales de rendimiento (CPU baseline — se actualizan cuando GPU esté activa)
THRESHOLD_7B_FIRST_TOKEN_S = 15.0  # segundos hasta primer token, modelo 7B
THRESHOLD_7B_TGEN_TPS = 3.0  # tokens/s mínimos aceptables en CPU
THRESHOLD_14B_FIRST_TOKEN_S = 30.0
THRESHOLD_EMBED_MS = 500  # ms por embedding
THRESHOLD_SOLVER_S = 5.0  # segundos para resolver un layout básico


def _ollama_chat_sync(model: str, prompt: str, system: str = "") -> dict[str, Any]:
    """Llamada síncrona a /api/chat para uso en benchmarks."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# BLOQUE 1 — Hardware
# ---------------------------------------------------------------------------


class TestHardwareDiagnostics:
    """Verifica el hardware disponible y reporta valores clave."""

    def test_cpu_info(self) -> None:
        """Informa número de CPUs lógicas disponibles."""
        import multiprocessing

        cpus = multiprocessing.cpu_count()
        print(f"\n  CPUs lógicas: {cpus}")
        assert cpus >= 4, f"Solo {cpus} CPUs detectadas. Mínimo esperado: 4"

    def test_ram_available(self) -> None:
        """Verifica que hay ≥ 16 GiB de RAM total."""
        # Alternativa portable: /proc/meminfo
        try:
            mem_info = Path("/proc/meminfo").read_text()
            mem_total_kb = int(
                next(line for line in mem_info.splitlines() if line.startswith("MemTotal")).split()[
                    1
                ]
            )
            mem_total_gib = mem_total_kb / (1024**2)
            print(f"\n  RAM total: {mem_total_gib:.1f} GiB")
            assert mem_total_gib >= 16.0, f"RAM total ({mem_total_gib:.1f} GiB) < 16 GiB"
        except Exception:
            pytest.skip("No se puede leer /proc/meminfo")

    def test_gpu_pci_present(self) -> None:
        """Verifica que la GPU AMD aparece en el bus PCI."""
        result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        output = result.stdout
        assert "amd" in output.lower() or "radeon" in output.lower() or "ati" in output.lower(), (
            "No se detectó GPU AMD en el bus PCI:\n" + result.stdout
        )
        gpu_lines = [
            line for line in result.stdout.splitlines() if "VGA" in line or "Display" in line
        ]
        print(f"\n  GPU detectada: {gpu_lines[0] if gpu_lines else 'n/a'}")

    def test_ollama_gpu_offloading(self) -> None:
        """
        CRÍTICO: Verifica que Ollama usa la GPU (size_vram > 0).

        Si falla, el rendimiento baja ~5-10x. Corrección:
          sudo systemctl edit ollama --force
          Añadir en [Service]:
            Environment="HSA_OVERRIDE_GFX_VERSION=10.3.0"
          sudo systemctl daemon-reload && sudo systemctl restart ollama
        """
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{OLLAMA_BASE}/api/ps")
            resp.raise_for_status()
            data = resp.json()

        models = data.get("models", [])
        if not models:
            pytest.skip("Ningún modelo cargado en Ollama ahora mismo")

        for m in models:
            vram = m.get("size_vram", 0)
            name = m.get("name", "?")
            print(f"\n  {name}: size_vram={vram / 1e9:.2f} GB")

        total_vram = sum(m.get("size_vram", 0) for m in models)
        assert total_vram > 0, (
            "FALLO GPU: size_vram=0 para todos los modelos. "
            "Ollama corre en CPU pura. "
            "Solución: añadir HSA_OVERRIDE_GFX_VERSION=10.3.0 al servicio."
        )

    def test_ollama_service_env_gpu(self) -> None:
        """Verifica que el servicio Ollama tiene la variable HSA_OVERRIDE_GFX_VERSION."""
        # Buscar tanto en el archivo principal como en los drop-ins
        files_to_check = [
            "/etc/systemd/system/ollama.service",
            "/etc/systemd/system/ollama.service.d/gpu.conf",
        ]
        combined = ""
        for fpath in files_to_check:
            r = subprocess.run(["cat", fpath], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                combined += r.stdout
        has_hsa = "HSA_OVERRIDE_GFX_VERSION" in combined
        has_vulkan = "OLLAMA_VULKAN=1" in combined
        print(f"\n  HSA_OVERRIDE_GFX_VERSION en servicio: {has_hsa}")
        print(f"  OLLAMA_VULKAN=1 en servicio: {has_vulkan}")
        assert has_hsa or has_vulkan, (
            "El servicio Ollama no tiene aceleración GPU configurada. "
            "Ver docs/decisions/0015-cierre-v1-0-estado-de-decisiones-acumuladas.md"
        )


# ---------------------------------------------------------------------------
# BLOQUE 2 — Ollama: conectividad y modelos
# ---------------------------------------------------------------------------


class TestOllamaConnectivity:
    """Verifica que Ollama responde y tiene los modelos requeridos."""

    def test_ollama_health(self) -> None:
        """Ollama responde en /."""
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(OLLAMA_BASE)
        assert resp.status_code == 200

    def test_required_models_available(self) -> None:
        """Todos los modelos de CLAUDE.md están disponibles localmente."""
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            available = {m["name"] for m in resp.json().get("models", [])}

        missing = [m for m in REQUIRED_MODELS if m not in available]
        print(f"\n  Modelos disponibles: {sorted(available)}")
        if missing:
            pytest.fail(
                f"Modelos requeridos faltantes: {missing}\nInstalar con: ollama pull <modelo>"
            )

    def test_ollama_embed_endpoint(self) -> None:
        """El endpoint de embeddings responde con vector de dimensión correcta."""
        with httpx.Client(timeout=30.0) as client:
            t0 = time.perf_counter()
            resp = client.post(
                f"{OLLAMA_BASE}/api/embed",
                json={"model": "nomic-embed-text", "input": "Gebäude"},
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            resp.raise_for_status()
            data = resp.json()

        embedding = data.get("embeddings", [[]])[0]
        print(f"\n  Dimensión embedding: {len(embedding)}, tiempo: {elapsed_ms:.0f} ms")
        assert len(embedding) == 768, f"Dimensión esperada 768, obtenida {len(embedding)}"
        assert elapsed_ms < THRESHOLD_EMBED_MS * 5, (
            f"Embedding demasiado lento: {elapsed_ms:.0f} ms (umbral: {THRESHOLD_EMBED_MS * 5} ms)"
        )


# ---------------------------------------------------------------------------
# BLOQUE 3 — Benchmark de inferencia
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestOllamaBenchmark:
    """Mide latencias y throughput de los modelos principales."""

    def _benchmark_model(
        self,
        model: str,
        prompt: str = "Sage mir kurz: wie viele Stockwerke hat ein Hochhaus?",
        n_runs: int = 1,
    ) -> dict[str, float]:
        """Mide tiempo total y estima tokens generados."""
        durations = []
        eval_counts = []
        for _ in range(n_runs):
            t0 = time.perf_counter()
            data = _ollama_chat_sync(model, prompt)
            elapsed = time.perf_counter() - t0
            durations.append(elapsed)
            # Ollama devuelve eval_count en la respuesta
            eval_counts.append(data.get("eval_count", 0))

        avg_s = statistics.mean(durations)
        avg_tokens = statistics.mean(eval_counts) if eval_counts[0] > 0 else 0
        tps = avg_tokens / avg_s if avg_s > 0 and avg_tokens > 0 else 0
        return {"avg_s": avg_s, "avg_tokens": avg_tokens, "tps": tps}

    def test_benchmark_7b_fast(self) -> None:
        """qwen2.5:7b responde en tiempo razonable."""
        model = "qwen2.5:7b-instruct-q4_K_M"
        result = self._benchmark_model(model)
        print(
            f"\n  [{model}] tiempo: {result['avg_s']:.1f}s, "
            f"tokens: {result['avg_tokens']:.0f}, "
            f"TPS: {result['tps']:.1f}"
        )
        assert result["avg_s"] < THRESHOLD_7B_FIRST_TOKEN_S, (
            f"Modelo 7B demasiado lento: {result['avg_s']:.1f}s "
            f"(umbral: {THRESHOLD_7B_FIRST_TOKEN_S}s). "
            "Probable causa: sin GPU offloading."
        )
        if result["tps"] > 0:
            assert result["tps"] >= THRESHOLD_7B_TGEN_TPS, (
                f"TPS insuficiente: {result['tps']:.1f} (mínimo: {THRESHOLD_7B_TGEN_TPS})"
            )

    def test_benchmark_14b_reasoning(self) -> None:
        """qwen2.5:14b responde en tiempo razonable."""
        model = "qwen2.5:14b-instruct-q4_K_M"
        result = self._benchmark_model(model)
        print(
            f"\n  [{model}] tiempo: {result['avg_s']:.1f}s, "
            f"tokens: {result['avg_tokens']:.0f}, "
            f"TPS: {result['tps']:.1f}"
        )
        assert result["avg_s"] < THRESHOLD_14B_FIRST_TOKEN_S, (
            f"Modelo 14B demasiado lento: {result['avg_s']:.1f}s "
            f"(umbral: {THRESHOLD_14B_FIRST_TOKEN_S}s)."
        )

    def test_benchmark_coder_7b(self) -> None:
        """qwen2.5-coder:7b responde en tiempo razonable."""
        model = "qwen2.5-coder:7b-instruct-q4_K_M"
        result = self._benchmark_model(
            model, "Write a Python function that sums a list of integers."
        )
        print(f"\n  [{model}] tiempo: {result['avg_s']:.1f}s, TPS: {result['tps']:.1f}")
        assert result["avg_s"] < THRESHOLD_7B_FIRST_TOKEN_S


# ---------------------------------------------------------------------------
# BLOQUE 4 — Agentes y grafo LangGraph
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestAgentPipeline:
    """Verifica el grafo LangGraph design_assistant end-to-end."""

    def test_design_assistant_import(self) -> None:
        """El módulo del grafo importa sin errores."""
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        from cimiento.llm.graphs.design_assistant import build_graph  # type: ignore

        graph = build_graph()
        assert graph is not None

    def test_design_assistant_regulation_query(self) -> None:
        """Una consulta normativa produce respuesta en alemán con referencia a norma."""
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        from cimiento.llm.graphs.design_assistant import (  # type: ignore
            DesignAssistantState,
            build_graph,
        )

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-reg-01"}}
        initial: DesignAssistantState = {
            "user_message": "Was sagt die MBO zu Mindesthöhen von Aufenthaltsräumen?",
            "extracted_params": None,
            "solution": None,
            "building": None,
            "validation_result": None,
            "user_response_de": None,
            "messages": [],
        }
        t0 = time.perf_counter()
        result = asyncio.get_event_loop().run_until_complete(graph.ainvoke(initial, config))
        elapsed = time.perf_counter() - t0
        response = result.get("user_response_de", "")
        print(f"\n  Respuesta normativa ({elapsed:.1f}s): {response[:200]}...")
        assert response, "El agente no produjo respuesta"
        assert elapsed < 60.0, f"Respuesta tardó {elapsed:.1f}s (umbral: 60s)"

    def test_design_assistant_full_design_flow(self) -> None:
        """
        Un mensaje completo de diseño traversa el grafo completo:
        extract → validate → solve → interpret.
        """
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        from cimiento.llm.graphs.design_assistant import (  # type: ignore
            DesignAssistantState,
            build_graph,
        )

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-design-01"}}
        initial: DesignAssistantState = {
            "user_message": (
                "Ich habe ein Grundstück von 20x30 Metern. "
                "Ich möchte ein 3-stöckiges Gebäude mit 4 Zweizimmerwohnungen planen."
            ),
            "extracted_params": None,
            "solution": None,
            "building": None,
            "validation_result": None,
            "user_response_de": None,
            "messages": [],
        }
        t0 = time.perf_counter()
        result = asyncio.get_event_loop().run_until_complete(graph.ainvoke(initial, config))
        elapsed = time.perf_counter() - t0
        response = result.get("user_response_de", "")
        print(f"\n  Respuesta diseño ({elapsed:.1f}s): {response[:300]}...")
        assert response, "El agente no produjo respuesta para petición de diseño"

    def test_tool_registry_completeness(self) -> None:
        """Todas las herramientas del registro son invocables."""
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        import inspect

        from cimiento.llm.tool_registry import ALL_REGISTERED_TOOLS  # type: ignore

        for name, fn in ALL_REGISTERED_TOOLS.items():
            assert callable(fn), f"Tool '{name}' no es callable"
            assert inspect.isfunction(fn) or inspect.iscoroutinefunction(fn), (
                f"Tool '{name}' no es una función"
            )
        print(f"\n  Tools registradas: {list(ALL_REGISTERED_TOOLS.keys())}")


# ---------------------------------------------------------------------------
# BLOQUE 5 — Solver CP-SAT
# ---------------------------------------------------------------------------


class TestSolverPerformance:
    """Verifica rendimiento del solver CP-SAT con casos reales."""

    def test_solver_basic_layout(self) -> None:
        """Solver resuelve un layout básico en menos de THRESHOLD_SOLVER_S segundos."""
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        from cimiento.schemas.geometry_primitives import Point2D, Polygon2D
        from cimiento.schemas.program import Program, TypologyMix
        from cimiento.schemas.solar import Solar
        from cimiento.schemas.typology import Room, RoomType, Typology
        from cimiento.solver.engine import solve  # type: ignore

        solar = Solar(
            id="test-solar",
            contour=Polygon2D(
                points=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=20.0, y=0.0),
                    Point2D(x=20.0, y=30.0),
                    Point2D(x=0.0, y=30.0),
                ]
            ),
            north_angle_deg=0.0,
            max_buildable_height_m=10.0,
        )
        program = Program(
            project_id="bench-001",
            num_floors=3,
            floor_height_m=3.0,
            typologies=[
                Typology(
                    id="T2",
                    name="Zweizimmerwohnung",
                    min_useful_area=70.0,
                    max_useful_area=95.0,
                    num_bedrooms=2,
                    num_bathrooms=1,
                    rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.0)],
                )
            ],
            mix=[TypologyMix(typology_id="T2", count=4)],
        )
        t0 = time.perf_counter()
        solution = solve(solar=solar, program=program)
        elapsed = time.perf_counter() - t0
        status_value = (
            solution.status.value if hasattr(solution.status, "value") else solution.status
        )
        print(f"\n  Solver: {elapsed:.2f}s, status={status_value}")
        assert elapsed < THRESHOLD_SOLVER_S, (
            f"Solver demasiado lento: {elapsed:.2f}s (umbral: {THRESHOLD_SOLVER_S}s)"
        )

    def test_solver_large_layout(self) -> None:
        """Solver maneja un edificio complejo (5 plantas, 20 unidades) en < 30s."""
        sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
        from cimiento.schemas.geometry_primitives import Point2D, Polygon2D
        from cimiento.schemas.program import Program, TypologyMix
        from cimiento.schemas.solar import Solar
        from cimiento.schemas.typology import Room, RoomType, Typology
        from cimiento.solver.engine import solve  # type: ignore

        solar = Solar(
            id="test-solar-large",
            contour=Polygon2D(
                points=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=30.0, y=0.0),
                    Point2D(x=30.0, y=40.0),
                    Point2D(x=0.0, y=40.0),
                ]
            ),
            north_angle_deg=0.0,
            max_buildable_height_m=17.0,
        )
        program = Program(
            project_id="bench-002",
            num_floors=5,
            floor_height_m=3.0,
            typologies=[
                Typology(
                    id="T2",
                    name="Zweizimmerwohnung",
                    min_useful_area=70.0,
                    max_useful_area=95.0,
                    num_bedrooms=2,
                    num_bathrooms=1,
                    rooms=[Room(type=RoomType.LIVING, min_area=20.0, min_short_side=3.0)],
                )
            ],
            mix=[TypologyMix(typology_id="T2", count=20)],
        )
        t0 = time.perf_counter()
        solution = solve(solar=solar, program=program)
        elapsed = time.perf_counter() - t0
        status_value = (
            solution.status.value if hasattr(solution.status, "value") else solution.status
        )
        print(f"\n  Solver grande: {elapsed:.2f}s, status={status_value}")
        assert elapsed < 30.0, f"Solver complejo tardó {elapsed:.2f}s (umbral: 30s)"


# ---------------------------------------------------------------------------
# BLOQUE 6 — Resumen de diagnóstico
# ---------------------------------------------------------------------------


class TestDiagnosticSummary:
    """Genera un resumen de diagnóstico completo del entorno."""

    def test_print_full_diagnostic(self) -> None:
        """Imprime diagnóstico completo del entorno."""
        import multiprocessing
        import platform

        print("\n" + "=" * 60)
        print("  DIAGNÓSTICO CIMIENTO v1.0")
        print("=" * 60)

        # OS y Python
        print(f"  OS:     {platform.system()} {platform.release()}")
        print(f"  Python: {platform.python_version()}")
        print(f"  CPUs:   {multiprocessing.cpu_count()}")

        # RAM
        try:
            mem = Path("/proc/meminfo").read_text()
            total = int(next(line for line in mem.splitlines() if "MemTotal" in line).split()[1])
            avail = int(
                next(line for line in mem.splitlines() if "MemAvailable" in line).split()[1]
            )
            print(
                f"  RAM:    {total / 1024**2:.1f} GiB total, {avail / 1024**2:.1f} GiB disponible"
            )
        except Exception:
            print("  RAM:    no disponible")

        # GPU
        try:
            gpu = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            gpus = [line for line in gpu.stdout.splitlines() if "VGA" in line or "Display" in line]
            for g in gpus:
                print(f"  GPU:    {g.strip()}")
        except Exception:
            print("  GPU:    no detectada")

        # Ollama
        try:
            with httpx.Client(timeout=5.0) as c:
                models = c.get(f"{OLLAMA_BASE}/api/tags").json().get("models", [])
                ps = c.get(f"{OLLAMA_BASE}/api/ps").json().get("models", [])
            print(f"  Ollama: {len(models)} modelos disponibles")
            for m in ps:
                vram = m.get("size_vram", 0)
                status = "GPU ✓" if vram > 0 else "CPU solo ⚠"
                print(f"    → {m['name']} [{status}, VRAM={vram / 1e9:.1f}GB]")

            # Verificar configuración del servicio (archivo principal + drop-ins)
            svc_files = [
                "/etc/systemd/system/ollama.service",
                "/etc/systemd/system/ollama.service.d/gpu.conf",
            ]
            svc_content = ""
            for f in svc_files:
                with suppress(FileNotFoundError):
                    svc_content += Path(f).read_text()
            hsa = "HSA_OVERRIDE_GFX_VERSION" in svc_content
            vulkan = "OLLAMA_VULKAN=1" in svc_content
            print(f"  HSA_OVERRIDE_GFX_VERSION configurado: {hsa}")
            print(f"  OLLAMA_VULKAN=1 configurado:           {vulkan}")
        except Exception as e:
            print(f"  Ollama: error — {e}")

        print("=" * 60)
        assert True  # siempre pasa, es diagnóstico

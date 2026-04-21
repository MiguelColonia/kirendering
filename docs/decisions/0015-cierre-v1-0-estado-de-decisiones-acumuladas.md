# ADR 0015 — Cierre v1.0: estado de decisiones acumuladas

**Estado:** Accepted  
**Fecha:** 2026-04-21  
**Decidido por:** Equipo Cimiento  
**Contexto:** Cierre de v1.0 con todas las fases funcionales y entrada en modo mantenimiento.

---

## Contexto

Tras completar las fases 1 a 8, el proyecto ya no necesita seguir tomando decisiones fundacionales dispersas sin una vista de conjunto. El repositorio acumula ADRs sobre solver, BIM, frontend, agentes, RAG, visión y render, pero faltaba un documento de cierre que dejara claro:

- qué decisiones quedan consolidadas en v1.0,
- qué ADRs siguen vigentes como contrato técnico,
- y qué cuestiones se consideran ajuste operativo para v1.x, no rediseño de arquitectura base.

El objetivo de esta ADR no es sustituir ninguna ADR anterior, sino servir como índice comentado y punto de entrada para mantenimiento.

---

## Decisión

Se declara que **no faltan ADRs críticos de primer nivel para cerrar v1.0** y se adopta esta ADR como **índice comentado oficial** de las decisiones acumuladas.

### Núcleo de optimización, geometría y BIM

- **ADR 0001 — OR-Tools como solver**
  Consolida que el cálculo espacial es determinista y queda fuera del LLM.
- **ADR 0002 — Qwen sobre Llama**
  Fija la familia de modelos locales base para razonamiento y extracción.
- **ADR 0003 — Formulación CP-SAT inicial**
  Deja establecida la base matemática del solver y su modo de evolución.
- **ADR 0004 — IFC4 como formato canónico**
  Consolida que IFC es la columna vertebral semántica del sistema.
- **ADR 0005 — Estrategia de muros y aberturas**
  Cierra la representación arquitectónica necesaria para BIM y exportaciones.
- **ADR 0006 — Solares poligonales**
  Amplía el dominio geométrico sin romper el contrato solver → BIM.

Estas decisiones se consideran plenamente consolidadas en v1.0.

### Producto web, agentes y normativa

- **ADR 0007 — Stack frontend para Fase 4**
  Consolida SPA React + TypeScript + Vite como cliente operativo del producto.
- **ADR 0008 — Cliente Ollama y modelos por rol**
  Fija el reparto de modelos locales por responsabilidad del agente.
- **ADR 0009 — Arquitectura de agentes con LangGraph**
  Establece el grafo conversacional y la separación estricta entre razonamiento y cálculo.
- **ADR 0010 — El agente normativo no razona**
  Limita el agente normativo a recuperar y citar, reduciendo alucinación jurídica.
- **ADR 0011 — RAG local y chunking por artículo**
  Consolida Qdrant + `nomic-embed-text` y el artículo jurídico como unidad primaria.

Estas decisiones también quedan consolidadas en v1.0 y forman el contrato de mantenimiento del copiloto conversacional.

### Ingesta visual y render

- **ADR 0012 — División OpenCV + VLM para ingesta visual**
  Cierra la responsabilidad dual entre extracción geométrica y semántica visual.
- **ADR 0013 — qwen2.5vl:7b para visión**
  Fija el VLM local preferente para interpretación de planos.
- **ADR 0014 — Estrategia SD para render**
  Consolida la dirección del pipeline de estilización y deja explícitas las restricciones multi-hardware.

En v1.0, estas ADRs dejan cerrada la arquitectura de entrada/salida visual. Lo que permanece abierto para v1.x no es el contrato general, sino la optimización práctica de tiempos, calidad y operación por hardware.

### Decisiones consolidadas en v1.0

Quedan consolidadas en v1.0 las siguientes premisas:

- el LLM orquesta, pero no resuelve geometría;
- CP-SAT sigue siendo el solver del producto;
- IFC4 sigue siendo el formato canónico;
- el frontend operativo es la SPA React en alemán orientada al mercado alemán;
- la normativa se consulta con RAG local y citas recuperadas;
- la visión requiere revisión humana antes de alimentar al solver;
- el render es una capa derivada del IFC y no altera el modelo BIM.

### Decisiones abiertas para v1.x

Se consideran abiertas para v1.x, sin invalidar v1.0:

- reevaluar IFC4.3 cuando el ecosistema de herramientas lo permita;
- endurecer persistencia del chat más allá de `MemorySaver`;
- ampliar corpus normativo por Land y tipología de edificio;
- optimizar la estrategia multi-hardware del render en AMD, Nvidia y cloud opt-in;
- mejorar profundidad/ControlNet con pases adicionales de Blender si el coste operativo compensa.

---

## Alternativas consideradas

### Opción A — Mantener solo `DECISIONS.md` como índice simple

Ventajas:

- menos documentación nueva;
- registro compacto.

Desventajas:

- no distingue entre lo consolidado en v1.0 y lo que sigue abierto;
- no aporta contexto suficiente para mantenimiento tras un parón.

### Opción B — Reescribir o fusionar todas las ADRs en un único documento maestro

Ventajas:

- un único punto de lectura.

Desventajas:

- destruye granularidad histórica;
- hace más difícil rastrear por qué se decidió cada pieza.

### Opción C — Añadir una ADR final de índice comentado (elegida)

Ventajas:

- conserva la historia completa;
- da una entrada clara para mantenimiento;
- permite declarar explícitamente el estado de v1.0.

Desventajas:

- añade un documento más al registro;
- exige mantener `DECISIONS.md` alineado con esta ADR.

---

## Consecuencias

- El proyecto queda documentado como **v1.0 funcional en mantenimiento**, no como una suma de fases inconexas.
- Los mantenedores tienen un punto de entrada claro para revisar decisiones antes de proponer cambios estructurales.
- No se detectan huecos críticos de ADR para el alcance ya entregado; por tanto, nuevas ADRs en v1.x deberán concentrarse en cambios reales de arquitectura o política técnica, no en reconstruir decisiones básicas ya cerradas.
- Esta ADR no reemplaza ninguna anterior; todas las ADRs 0001-0014 siguen vigentes salvo futura deprecación explícita.

---

## Estado

**Accepted**.
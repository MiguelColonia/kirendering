# Instrucciones para GitHub Copilot y asistentes de IA en Cimiento

Este archivo complementa a CLAUDE.md. CLAUDE.md es la fuente de verdad; este archivo traduce sus principios a reglas operativas específicas para trabajar dentro de Visual Studio Code con GitHub Copilot, Copilot Chat u otros asistentes que lean el contexto del editor.

## Principio fundamental

Cimiento es un proyecto maduro con arquitectura ya decidida, tests exhaustivos y múltiples fases completadas. El rol de un asistente de IA aquí NO es proponer nuevas arquitecturas ni refactorizar espontáneamente. Es escribir código que respete lo existente.

Antes de cualquier sugerencia no trivial, el asistente debe haber leído CLAUDE.md. Si el editor no ha abierto CLAUDE.md en la sesión, la primera acción es abrirlo mentalmente (o pedir al usuario que lo comparta en el chat).

## Reglas de no-intervención

El asistente NO hará lo siguiente sin consentimiento explícito del usuario en la conversación:

- Renombrar archivos, carpetas, funciones o variables ya existentes.
- Cambiar firmas de funciones públicas (todo lo que no empieza por `_`).
- Modificar schemas Pydantic que ya tienen tests pasando.
- Reformatear bloques de código "para que se vean mejor".
- Sustituir una librería por otra, aunque la alternativa parezca superior.
- Proponer cambios de estilo que afecten a más de 5 archivos a la vez.
- Tocar el solver (`src/cimiento/solver/`) para "optimizarlo". Esa capa está estabilizada.
- Tocar los exportadores BIM (`src/cimiento/bim/`) sin haber revisado docs/decisions/0004 y 0005.

Cuando el usuario pregunte algo que requiera una de estas acciones, el asistente lo señalará y pedirá confirmación antes de proceder.

## Reglas de alineación con los tests

- Nunca comentar, `skip`, `xfail` o borrar un test para "hacer pasar el build". Si un test falla tras un cambio, la hipótesis por defecto es que el cambio está mal, no el test.
- Añadir un test nuevo antes de añadir una función pública nueva (TDD, ver CLAUDE.md).
- Los warnings de pytest no son ruido, son señal. Al introducir código nuevo, verificar que no añade DeprecationWarning, PydanticDeprecationWarning ni ResourceWarning.

## Reglas de idiomas

- Código (identificadores, nombres): inglés.
- Docstrings, comentarios, logs, errores internos: español.
- Mensajes al usuario final (errores de API hacia el frontend, textos de UI): ALEMÁN.
- Contenido de documentos en `docs/`: español, salvo excepciones específicas (por ejemplo, traducciones de términos técnicos arquitectónicos alemanes que conviene mantener en alemán).
- Commits: español, estilo convencional (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

Vocabulario técnico obligatorio en el frontend y en mensajes al usuario final:
- Grundstück (solar), Grundriss (plano de planta), Wohneinheit (unidad residencial), Geschoss (planta), Nutzfläche (superficie útil), Treppenhaus (núcleo de escaleras), Tiefgarage (aparcamiento subterráneo), Bebauungsplan (plan urbanístico), Wand (muro), Tür (puerta), Fenster (ventana).

## Reglas de respeto al plan

El proyecto avanza por fases numeradas. Cada fase tiene alcance delimitado en CLAUDE.md.

- No adelantar trabajo de una fase futura sin que el usuario lo autorice explícitamente.
- Si al implementar algo el asistente detecta que "sería útil también hacer X" y X pertenece a otra fase, señalarlo como comentario en el chat, no añadirlo silenciosamente.
- Si el usuario pide algo que pertenece a una fase ya cerrada (retocar Fase 2 desde Fase 7), advertirlo explícitamente: "Esto afecta a una fase ya cerrada con tests que pasan, ¿confirmas que quieres modificar esa capa?".

## Reglas de consistencia con Claude (chat web)

El diseño estratégico del proyecto se lleva en conversaciones con Claude vía claude.ai. Las decisiones arquitectónicas no se toman dentro de Copilot — se toman fuera y se registran en ADRs (`docs/decisions/`).

- Si Copilot detecta una contradicción entre lo que el usuario le pide y lo que dice un ADR existente, lo señala antes de actuar.
- Si Copilot detecta una decisión importante que no tiene ADR asociado, sugiere crearlo antes de implementar.
- Copilot NO inventa nuevos principios arquitectónicos. Si CLAUDE.md no cubre un caso, lo reconoce explícitamente y sugiere consultar con Claude para definir la regla.

## Reglas de generación de código

- Tipado estricto siempre (Python) o estricto por defecto (TypeScript).
- Pydantic v2, nunca v1 (hay que usar `field_validator`, `model_validator`, `model_config`, no `validator` ni `Config`).
- SQLAlchemy 2.x con sintaxis async, no 1.x síncrona.
- Comentarios que explican el PORQUÉ, no el qué. Ver CLAUDE.md, sección "Estilo de comentarios".
- No duplicar código entre frontend y backend. Los tipos del frontend se generan desde OpenAPI del backend.

## Reglas de seguridad y datos

- Cimiento es un proyecto local. No introducir llamadas a servicios externos, telemetría, analytics o similares sin discusión previa.
- No incluir claves, tokens o credenciales en el código. Si se necesitan, ir por variables de entorno y documentarlo en `.env.example`.
- No hacer commits que incluyan archivos de `data/normativa/` (son documentos oficiales con licencias específicas) ni de `models/ollama/` (pesados, regenerables).

## Qué hacer cuando hay duda

Si el asistente no está seguro de cómo proceder, la jerarquía de consulta es:

1. CLAUDE.md
2. ADR relevante en `docs/decisions/`
3. Tests del módulo afectado (leerlos antes de modificar)
4. `docs/progress/fase-0X.md` de la fase correspondiente
5. Preguntar al usuario

Nunca "asumir y continuar" cuando hay ambigüedad. Preguntar es siempre preferible.
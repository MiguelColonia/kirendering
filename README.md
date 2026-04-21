# Cimiento

## 🇪🇸 Español

### Descripción

Cimiento es un copiloto local de anteproyecto residencial para el mercado alemán. Combina conversación asistida por LLM, optimización espacial determinista, generación BIM abierta, consulta normativa con RAG, lectura visual de planos y render fotorrealista a partir del IFC canónico. Todo el flujo está pensado para ejecutarse en local, bajo control del estudio y sin enviar los datos del proyecto a servicios externos por defecto.

En v1.0 el producto ya cubre el ciclo completo de trabajo: crear proyecto, definir Grundstück y programa, generar propuesta, revisar el IFC en 3D, conversar con el copiloto, exportar IFC/DXF/XLSX y producir renders de presentación.

### Capacidades principales

- Creación y versionado de proyectos residenciales con solar editable.
- Optimización espacial con OR-Tools CP-SAT, separada del razonamiento LLM.
- Generación BIM abierta con IFC4 como formato canónico.
- Exportaciones derivadas en DXF, XLSX y SVG.
- Visor IFC web con navegación espacial, propiedades y recortes por Geschoss.
- Copiloto conversacional con LangGraph y modelos locales en Ollama.
- Consulta normativa local con Qdrant + embeddings y citas trazables.
- Ingesta visual de planos 2D con OpenCV + VLM bajo revisión humana.
- Galería de renders con progreso, referencia visual opcional y descarga HQ.

### Capturas de pantalla

![Landing de Cimiento](docs/images/placeholder.png)

![Editor de proyecto y generación](docs/images/placeholder.png)

![Visor IFC y chat del copiloto](docs/images/placeholder.png)

![Galería de renders](docs/images/placeholder.png)

Las capturas pendientes y su contenido previsto están descritas en [docs/images/.README.md](docs/images/.README.md).

### Vídeo demo

El vídeo de demostración final se alojará en `docs/demo/video.mp4` cuando el usuario lo grabe. El guion detallado y el proceso recomendado para capturarlo están en [docs/demo/guion-video-demo.md](docs/demo/guion-video-demo.md) y [docs/demo/README.md](docs/demo/README.md).

Marcador para insertar el enlace definitivo:

`[VIDEO_DEMO_AQUI]`

### Instalación

Hardware mínimo orientativo:

- Linux x86_64.
- Python 3.11+ y Node.js 22 para desarrollo local.
- Docker Engine + Docker Compose plugin.
- Blender 4.x para la parte de render.
- 16 GB RAM como mínimo práctico; 32 GB recomendados.
- GPU dedicada recomendada para IA y render; CPU-only es posible con limitaciones severas.

Ruta recomendada de instalación:

1. Elegir la guía según el hardware en [docs/installation/README.md](docs/installation/README.md).
2. Instalar dependencias base del sistema, Docker, Ollama y herramientas Python.
3. Descargar los modelos locales requeridos.
4. Levantar el stack en modo desarrollo o producción según [infra/docker/README.md](infra/docker/README.md).
5. Ejecutar una primera verificación funcional: proyecto, generación, visor IFC, chat y render.

### Arquitectura

Cimiento separa estrictamente razonamiento, optimización y materialización BIM; el resumen arquitectónico está en [docs/architecture/README.md](docs/architecture/README.md).

### Licencia

La licencia definitiva sigue pendiente de confirmación del titular. Estado actual en [LICENSE](LICENSE).

### Créditos

- Dirección de producto y arquitectura: proyecto Cimiento.
- Stack principal: FastAPI, React, OR-Tools, IfcOpenShell, LangGraph, Ollama, Qdrant, Blender.
- Ecosistema BIM/visualización: That Open Components, web-ifc, three.js.

---

## 🇩🇪 Deutsch

### Kurzbeschreibung

Cimiento ist ein lokal betriebenes Copilot-System fuer den Wohnungsentwurf im deutschen Markt. Es verbindet dialoggestuetzte Assistenz, deterministische Grundrissoptimierung, offene BIM-Erzeugung, normbezogenes RAG, visuelle Planinterpretation und fotorealistisches Rendering auf Basis des kanonischen IFC-Modells. Standardmaessig bleibt der komplette Projektfluss lokal und unter Kontrolle des Bueros.

In v1.0 deckt das Produkt bereits den vollstaendigen Arbeitsablauf ab: Projekt anlegen, Grundstück und Programm definieren, Entwurf berechnen, IFC im Browser pruefen, mit dem Copiloten sprechen, IFC/DXF/XLSX exportieren und Praesentationsrenders erzeugen.

### Hauptfunktionen

- Anlage und Versionierung von Wohnprojekten mit editierbarem Grundstück.
- Deterministische Flaechen- und Layoutoptimierung mit OR-Tools CP-SAT.
- Offene BIM-Erzeugung mit IFC4 als semantischem Rueckgrat.
- Abgeleitete Exporte in DXF, XLSX und SVG.
- Webbasierter IFC-Viewer mit Strukturbaum, Eigenschaften und Geschoss-Schnitten.
- Konversationscopilot mit LangGraph und lokalen Ollama-Modellen.
- Lokale Normabfrage ueber Qdrant und Embeddings mit nachvollziehbaren Zitaten.
- Bildgestuetzte Planaufnahme ueber OpenCV + VLM mit verpflichtender menschlicher Pruefung.
- Render-Galerie mit Fortschritt, optionalem Referenzbild und HQ-Download.

### Screenshots

![Cimiento Landingpage](docs/images/placeholder.png)

![Projekteditor und Generierung](docs/images/placeholder.png)

![IFC-Viewer und Copilot-Chat](docs/images/placeholder.png)

![Render-Galerie](docs/images/placeholder.png)

Die noch fehlenden Screenshots und ihre geplanten Inhalte sind in [docs/images/.README.md](docs/images/.README.md) beschrieben.

### Demo-Video

Das finale Demo-Video wird spaeter unter `docs/demo/video.mp4` abgelegt, sobald es manuell aufgenommen wurde. Drehbuch und Aufnahmeprozess befinden sich in [docs/demo/guion-video-demo.md](docs/demo/guion-video-demo.md) und [docs/demo/README.md](docs/demo/README.md).

Platzhalter fuer den spaeteren Link:

`[VIDEO_DEMO_AQUI]`

### Installation

Praktische Mindestvoraussetzungen:

- Linux x86_64.
- Python 3.11+ und Node.js 22 fuer lokale Entwicklung.
- Docker Engine + Docker Compose Plugin.
- Blender 4.x fuer den Render-Pfad.
- Mindestens 16 GB RAM; empfohlen sind 32 GB.
- Dedizierte GPU fuer KI und Render empfohlen; CPU-only bleibt ein eingeschraenkter Modus.

Empfohlene Reihenfolge:

1. Passende Hardware-Anleitung in [docs/installation/README.md](docs/installation/README.md) auswaehlen.
2. Systempakete, Docker, Ollama und Python-Werkzeuge installieren.
3. Benoetigte lokale Modelle herunterladen.
4. Entwicklungs- oder Produktionsstack nach [infra/docker/README.md](infra/docker/README.md) starten.
5. Einen ersten End-to-End-Test fuer Projekt, Generierung, IFC-Viewer, Chat und Render ausfuehren.

### Architektur

Cimiento trennt strikt zwischen Reasoning, Optimierung und BIM-Materialisierung; der Architekturueberblick steht in [docs/architecture/README.md](docs/architecture/README.md).

### Lizenz

Die endgueltige Lizenz ist noch nicht freigegeben. Der aktuelle Zwischenstand steht in [LICENSE](LICENSE).

### Credits

- Produkt- und Architekturleitung: Projekt Cimiento.
- Kernstack: FastAPI, React, OR-Tools, IfcOpenShell, LangGraph, Ollama, Qdrant, Blender.
- BIM- und Visualisierungs-Stack: That Open Components, web-ifc, three.js.

# Guion de vídeo demo / Drehbuch Demo-Video

Duración objetivo / Zielzeit: **3-5 minutos**

---

## Español

### Escena 1 — Landing

- Tiempo estimado: `00:00-00:20`
- En pantalla: portada de Cimiento, navegación principal y acceso a proyectos.
- Input en UI: ninguno.
- Voz en off:

  "Cimiento es un copiloto local para anteproyecto residencial. En una sola herramienta combina conversación, optimización espacial, BIM abierto, normativa y render de presentación, todo manteniendo el IFC como columna vertebral del sistema."

### Escena 2 — Crear proyecto

- Tiempo estimado: `00:20-00:50`
- En pantalla: lista de proyectos y apertura del diálogo de creación.
- Input en UI:
  - Nombre: `Mehrfamilienhaus Berlin Mitte`
  - Descripción: `Projekt demo für Wohnungsentwurf mit Innenhof`
- Voz en off:

  "Empezamos creando un proyecto nuevo. Cimiento versiona desde el primer momento el solar y el programa, de forma que cada iteración posterior queda trazada y puede compararse con las anteriores."

### Escena 3 — Dibujar solar

- Tiempo estimado: `00:50-01:25`
- En pantalla: editor de solar, manipulación de vértices del polígono.
- Input en UI:
  - Ajustar el polígono a un solar aproximado de `28 x 42 m` con un retranqueo lateral.
- Voz en off:

  "Aquí definimos el Grundstück directamente en la interfaz. El sistema trabaja con polígonos reales, así que no se limita a parcelas rectangulares simples."

### Escena 4 — Configurar programa

- Tiempo estimado: `01:25-02:00`
- En pantalla: editor del programa residencial.
- Input en UI:
  - `6 Geschosse`
  - Tipología `T2`, `12` unidades
  - Tipología `T3`, `6` unidades
- Voz en off:

  "Después configuramos el programa: número de Geschosse, tipologías y mezcla de viviendas. El copiloto no calcula geometría; la parte espacial la resolverá después el solver determinista."

### Escena 5 — Generar

- Tiempo estimado: `02:00-02:25`
- En pantalla: botón de generación y panel de progreso.
- Input en UI:
  - Clic en `Entwurf generieren`
- Voz en off:

  "Con un solo paso lanzamos la generación completa. La interfaz muestra el progreso del solver, la construcción BIM y la fase de exportación en tiempo real."

### Escena 6 — IFC en 3D

- Tiempo estimado: `02:25-02:55`
- En pantalla: visor IFC, árbol espacial, selección de elementos.
- Input en UI:
  - Abrir pestaña `Modell`
  - Seleccionar un Geschoss y un elemento IFC
- Voz en off:

  "El resultado no es una imagen plana: es un modelo IFC navegable. Podemos revisar la estructura espacial, inspeccionar propiedades y validar el edificio antes de exportarlo o presentarlo."

### Escena 7 — Chat con el copiloto

- Tiempo estimado: `02:55-03:30`
- En pantalla: panel de chat abierto.
- Input en UI:
  - Mensaje: `Prüfe bitte, ob das Programm für dieses Grundstück plausibel ist und welche Risiken du siehst.`
- Voz en off:

  "El copiloto conversa en alemán y orquesta agentes especializados. Puede analizar el planteamiento, consultar normativa recuperada localmente y explicar riesgos sin invadir la capa geométrica."

### Escena 8 — Exportar IFC, DXF y XLSX

- Tiempo estimado: `03:30-03:55`
- En pantalla: sección de descargas.
- Input en UI:
  - Descargar `IFC`, `DXF` y `XLSX`
- Voz en off:

  "Desde la misma vista descargamos el IFC canónico y sus derivados de trabajo: DXF para CAD y XLSX para control de superficies y programa."

### Escena 9 — Generar render

- Tiempo estimado: `03:55-04:40`
- En pantalla: ruta `/projekte/:id/renders`, formulario `Neuer Render`, progreso y galería.
- Input en UI:
  - Vista: `Außenansicht`
  - Prompt: `Heller Wohnbau mit warmer Abendsonne und ruhiger Materialität`
  - Imagen de referencia: opcional
  - Clic en `Render starten`
- Voz en off:

  "Para cerrar el flujo, Cimiento genera un render de presentación a partir del IFC. El trabajo se sigue con barra de progreso, se archiva en la galería del proyecto y puede descargarse en alta calidad."

### Plano final

- Tiempo estimado: `04:40-05:00`
- En pantalla: galería de renders y regreso breve al nombre del proyecto.
- Voz en off:

  "Este es el alcance de Cimiento v1.0: del solar y el programa al BIM, la conversación asistida, la normativa y la imagen final, todo en un flujo local y controlado por el estudio."

---

## Deutsch

### Szene 1 — Landingpage

- Geschätzte Zeit: `00:00-00:20`
- Auf dem Bildschirm: Startseite von Cimiento, Hauptnavigation und Einstieg in die Projekte.
- Eingabe in der UI: keine.
- Sprechertext:

  "Cimiento ist ein lokal betriebener Copilot fuer den Wohnungsentwurf. In einem einzigen Werkzeug verbindet es Gespraech, Grundrissoptimierung, offenes BIM, Normrecherche und Praesentationsrendering, wobei das IFC-Modell immer das semantische Rueckgrat bildet."

### Szene 2 — Projekt anlegen

- Geschätzte Zeit: `00:20-00:50`
- Auf dem Bildschirm: Projektliste und geoeffneter Anlagedialog.
- Eingabe in der UI:
  - Name: `Mehrfamilienhaus Berlin Mitte`
  - Beschreibung: `Projekt demo für Wohnungsentwurf mit Innenhof`
- Sprechertext:

  "Wir starten mit einem neuen Projekt. Cimiento versioniert Grundstück und Programm von Beginn an, damit jede spaetere Iteration nachvollziehbar und mit frueheren Staenden vergleichbar bleibt."

### Szene 3 — Grundstück zeichnen

- Geschätzte Zeit: `00:50-01:25`
- Auf dem Bildschirm: Grundstückseditor, Verschieben der Polygonpunkte.
- Eingabe in der UI:
  - Polygon auf ein Grundstueck von etwa `28 x 42 m` mit seitlichem Ruecksprung einstellen.
- Sprechertext:

  "Hier definieren wir das Grundstück direkt in der Oberflaeche. Das System arbeitet mit echten Polygonen und ist deshalb nicht auf einfache Rechtecke beschraenkt."

### Szene 4 — Programm konfigurieren

- Geschätzte Zeit: `01:25-02:00`
- Auf dem Bildschirm: Editor fuer das Wohnprogramm.
- Eingabe in der UI:
  - `6 Geschosse`
  - Typologie `T2`, `12` Einheiten
  - Typologie `T3`, `6` Einheiten
- Sprechertext:

  "Anschliessend konfigurieren wir das Programm: Anzahl der Geschosse, Typologien und den Wohnungsmix. Der Copilot rechnet keine Geometrie; die raeumliche Aufloesung uebernimmt spaeter der deterministische Solver."

### Szene 5 — Generierung starten

- Geschätzte Zeit: `02:00-02:25`
- Auf dem Bildschirm: Generierungsbutton und Fortschrittspanel.
- Eingabe in der UI:
  - Klick auf `Entwurf generieren`
- Sprechertext:

  "Mit einem Schritt starten wir den gesamten Ablauf. Die Oberflaeche zeigt Solver, BIM-Aufbau und Export in Echtzeit."

### Szene 6 — IFC in 3D pruefen

- Geschätzte Zeit: `02:25-02:55`
- Auf dem Bildschirm: IFC-Viewer, Strukturbaum und Elementeigenschaften.
- Eingabe in der UI:
  - Tab `Modell` oeffnen
  - Ein Geschoss und ein IFC-Element auswaehlen
- Sprechertext:

  "Das Ergebnis ist kein statisches Bild, sondern ein navigierbares IFC-Modell. Wir koennen die raeumliche Struktur pruefen, Eigenschaften kontrollieren und das Gebaeude vor Export oder Praesentation fachlich abnehmen."

### Szene 7 — Chat mit dem Copiloten

- Geschätzte Zeit: `02:55-03:30`
- Auf dem Bildschirm: geoeffnetes Chatpanel.
- Eingabe in der UI:
  - Nachricht: `Prüfe bitte, ob das Programm für dieses Grundstück plausibel ist und welche Risiken du siehst.`
- Sprechertext:

  "Der Copilot arbeitet auf Deutsch und orchestriert spezialisierte Agenten. Er kann den Ansatz einschaetzen, lokal recherchierte Normtexte einbeziehen und Risiken erklaeren, ohne die geometrische Loesungsschicht zu verletzen."

### Szene 8 — IFC, DXF und XLSX exportieren

- Geschätzte Zeit: `03:30-03:55`
- Auf dem Bildschirm: Download-Bereich.
- Eingabe in der UI:
  - `IFC`, `DXF` und `XLSX` herunterladen
- Sprechertext:

  "Aus derselben Projektansicht laden wir das kanonische IFC und die abgeleiteten Arbeitsformate herunter: DXF fuer CAD und XLSX fuer Flaechen- und Programmkontrolle."

### Szene 9 — Render erzeugen

- Geschätzte Zeit: `03:55-04:40`
- Auf dem Bildschirm: Route `/projekte/:id/renders`, Formular `Neuer Render`, Fortschritt und Galerie.
- Eingabe in der UI:
  - Ansicht: `Außenansicht`
  - Prompt: `Heller Wohnbau mit warmer Abendsonne und ruhiger Materialität`
  - Referenzbild: optional
  - Klick auf `Render starten`
- Sprechertext:

  "Zum Abschluss erzeugt Cimiento ein Praesentationsrender direkt aus dem IFC. Der Auftrag wird mit Fortschrittsanzeige verfolgt, in der Projektgalerie abgelegt und kann in hoher Qualitaet heruntergeladen werden."

### Schlussbild

- Geschätzte Zeit: `04:40-05:00`
- Auf dem Bildschirm: Render-Galerie und kurzer Ruecksprung auf den Projektnamen.
- Sprechertext:

  "Das ist der Umfang von Cimiento v1.0: vom Grundstück und Programm ueber BIM, Copilot und Normrecherche bis zum finalen Bild, alles in einem lokalen und kontrollierten Workflow."
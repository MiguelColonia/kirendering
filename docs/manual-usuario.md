# Manual de usuario / Benutzerhandbuch

## Español

### Propósito

Este documento describe el uso operativo de Cimiento v1.0 desde la perspectiva de usuario. No sustituye a las guías de instalación; asume que el sistema ya está desplegado y que backend, frontend, Docker y Ollama funcionan correctamente.

### Qué es Cimiento

Cimiento es un copiloto local de anteproyecto residencial para el mercado alemán. El flujo de trabajo une creación de proyecto, edición del solar, definición del programa, generación determinista del anteproyecto, revisión BIM en IFC, consulta conversacional, análisis visual de planos y producción de renders o variaciones generativas.

### Requisitos previos de uso

- El frontend debe estar accesible normalmente en `http://localhost:8080`.
- El backend debe responder normalmente en `http://localhost:8000`.
- Ollama debe estar activo si se va a usar chat, análisis visual o funciones asistidas por modelos.
- Para render y difusión, Blender y la aceleración disponible en la máquina deben estar correctamente configurados.

### Flujo correcto de trabajo

1. Crear el proyecto.
2. Definir el `Grundstück`.
3. Definir el `Programm`.
4. Guardar los cambios.
5. Lanzar la generación del anteproyecto.
6. Revisar el modelo IFC y las exportaciones.
7. Consultar al asistente o analizar planos si hace falta.
8. Generar renders o variantes visuales solo al final.

### 1. Crear un proyecto

Desde la pantalla inicial puede abrir la lista de proyectos o pulsar `Neues Projekt`. La creación del proyecto se realiza en un diálogo que pide:

- nombre del proyecto,
- descripción opcional,
- solar inicial,
- programa inicial.

El primer guardado ya crea una versión útil del proyecto. No está pensado como un formulario vacío para completar más tarde sin estructura.

### 2. Definir correctamente el solar

En la pestaña `Grundstück` se edita el polígono del solar directamente sobre el canvas.

Buenas prácticas:

- use al menos tres puntos,
- evite autointersecciones,
- compruebe que la geometría representa realmente el solar de trabajo,
- defina una altura edificable máxima positiva,
- ajuste la orientación norte si afecta a la lectura del proyecto.

Si el solar no es válido, Cimiento bloquea el guardado o avisa de que la entrada todavía no es aceptable para un anteproyecto serio.

### 3. Definir correctamente el programa

En la pestaña `Programm` se configuran las tipologías, el mix y los parámetros globales del edificio.

Para usarlo bien:

- cree al menos una tipología,
- asegúrese de que cada tipología tenga un identificador claro,
- mantenga coherencia entre tipologías y mix,
- defina un número de `Geschosse` realista,
- use alturas de planta positivas,
- revise el total de viviendas antes de generar.

Si el programa es inconsistente, la aplicación mostrará errores de validación y no conviene forzar el siguiente paso.

### 4. Guardar antes de generar

La generación no debe entenderse como autoguardado. El uso correcto consiste en guardar primero los cambios del solar y del programa y, después, pulsar `Entwurf generieren`.

Este paso activa tres bloques internos:

1. solver,
2. construcción BIM,
3. exportación.

La interfaz muestra fases, estado y errores del trabajo en segundo plano.

### 5. Interpretar bien el resultado de la generación

Si la generación termina con éxito, el proyecto pasa a un estado factible u óptimo y aparece el acceso al modelo.

Si la generación falla con una solución no factible:

- reduzca viviendas,
- suavice restricciones,
- revise alturas y programa,
- confirme que el solar tiene suficiente capacidad.

No es recomendable tratar un resultado `infeasible` como un fallo aleatorio del sistema. En la mayoría de casos expresa incompatibilidad entre restricciones de entrada.

### 6. Revisar el modelo IFC

La pestaña `Modell` solo aparece cuando existe una salida IFC para la versión actual del proyecto.

En esta vista puede:

- navegar por el árbol espacial del modelo,
- seleccionar elementos,
- revisar propiedades IFC,
- cambiar la proyección,
- enfocar el modelo completo,
- hacer cortes horizontales por planta,
- descargar IFC, DXF, XLSX y SVG.

Uso recomendado:

- revise primero la estructura general del edificio,
- compruebe plantas y elementos singulares,
- use propiedades y árbol para detectar incoherencias,
- descargue exportaciones solo después de una revisión mínima.

### 7. Usar correctamente el asistente conversacional

El `KI-Assistent` es un panel lateral contextual del proyecto. Sirve para:

- hacer preguntas sobre el proyecto,
- pedir explicaciones sobre la solución generada,
- consultar restricciones o normativa,
- explorar ajustes antes de volver a editar el proyecto.

No debe usarse para sustituir al solver geométrico. La geometría válida del sistema sigue viniendo del flujo determinista de generación.

Limitación importante:

- el historial del chat no se conserva al cambiar de página.

### 8. Analizar planos 2D con revisión humana

La acción `Grundriss analysieren` permite subir una imagen o escaneo de plano para detectar espacios, etiquetas y símbolos.

Este módulo debe usarse así:

- como ayuda de lectura,
- como borrador inicial,
- nunca como verdad final sin revisión.

El propio producto advierte que todos los resultados son aproximados y deben validarse manualmente antes de reutilizarlos.

### 9. Generar renders correctamente

La `Rendergalerie` pertenece al proyecto actual. El render siempre parte del IFC más reciente.

Flujo recomendado:

1. generar antes el proyecto con salida IFC,
2. abrir la galería,
3. elegir vista exterior o interior,
4. añadir un prompt en alemán si hace falta,
5. subir una imagen de referencia opcional,
6. lanzar el render y seguir el progreso.

La UI muestra porcentaje, estado del trabajo, eventos recientes y tiempo estimado. El resultado final queda en galería con descarga en alta calidad.

### 10. Usar difusión para variantes visuales

La función `KI-Bild erstellen` sirve para producir o refinar imágenes a partir de una imagen base. Ofrece tres modos principales:

- ControlNet con profundidad,
- ControlNet con bordes,
- InstructPix2Pix.

Uso correcto:

- úselo para explorar estilo, materialidad o atmósfera,
- no lo use como sustituto del modelo IFC,
- trate la salida como derivada visual, no como modificación geométrica del proyecto.

### Recomendaciones operativas

- Trabaje en este orden: solar, programa, generación, revisión, imagen.
- Use el visor IFC como control de calidad antes de exportar o presentar.
- Escriba los prompts de render y difusión en alemán para mantener coherencia con la UI del producto.
- Si hay errores en chat, visión o difusión, revise primero Ollama, GPU disponible y memoria antes de asumir un bug del producto.

### Limitaciones importantes

- El chat no persiste entre páginas.
- La pestaña de modelo depende de que exista IFC.
- El análisis visual requiere revisión humana obligatoria.
- Render y difusión dependen del hardware y pueden tardar varios minutos.
- Las imágenes generadas no sustituyen el modelo BIM validado.

---

## Deutsch

### Zweck

Dieses Dokument beschreibt die operative Nutzung von Cimiento v1.0 aus Anwendersicht. Es ersetzt nicht die Installationsanleitungen; vorausgesetzt wird ein bereits funktionierendes System mit betriebsbereitem Backend, Frontend, Docker und Ollama.

### Was Cimiento ist

Cimiento ist ein lokal betriebenes Copilot-System fuer den Wohnungsentwurf im deutschen Markt. Der Arbeitsablauf verbindet Projektanlage, Grundstücksbearbeitung, Programmdefinition, deterministische Entwurfsgenerierung, IFC-Pruefung, konversationelle Assistenz, visuelle Plananalyse sowie Rendering und generative Bildvarianten.

### Voraussetzungen fuer den Betrieb

- Das Frontend sollte normalerweise unter `http://localhost:8080` erreichbar sein.
- Das Backend sollte normalerweise unter `http://localhost:8000` antworten.
- Ollama muss aktiv sein, wenn Chat, Bildanalyse oder modellgestuetzte Funktionen verwendet werden sollen.
- Fuer Render und Diffusion muessen Blender und die verfuegbare Beschleunigung auf dem Host korrekt eingerichtet sein.

### Empfohlener Arbeitsablauf

1. Projekt anlegen.
2. `Grundstück` definieren.
3. `Programm` definieren.
4. Aenderungen speichern.
5. Entwurfsgenerierung starten.
6. IFC-Modell und Exporte pruefen.
7. Assistenten oder Plananalyse bei Bedarf nutzen.
8. Renderings oder Bildvarianten erst zum Schluss erzeugen.

### 1. Ein Projekt anlegen

Auf der Startseite koennen Sie entweder die Projektliste oeffnen oder `Neues Projekt` waehlen. Die Projektanlage erfolgt in einem Dialog mit folgenden Angaben:

- Projektname,
- optionale Beschreibung,
- initiales Grundstück,
- initiales Programm.

Das erste Speichern erzeugt bereits eine nutzbare Projektversion. Der Dialog ist nicht als leere Zwischenablage gedacht, die spaeter ohne Struktur nachgepflegt wird.

### 2. Das Grundstück korrekt definieren

In der Registerkarte `Grundstück` wird das Polygon direkt im Canvas bearbeitet.

Bewaehrte Nutzung:

- mindestens drei Punkte verwenden,
- Selbstueberschneidungen vermeiden,
- sicherstellen, dass die Geometrie das reale Grundstück korrekt repraesentiert,
- eine positive maximale Gebaeudehoehe setzen,
- die Nordausrichtung sinnvoll anpassen.

Wenn das Grundstück ungueltig ist, blockiert Cimiento das Speichern oder weist darauf hin, dass die Eingabe noch nicht fuer einen belastbaren Vorentwurf geeignet ist.

### 3. Das Programm korrekt definieren

In der Registerkarte `Programm` werden Typologien, Mix und globale Gebaeudeparameter konfiguriert.

Fuer eine saubere Nutzung:

- mindestens eine Typologie anlegen,
- jeder Typologie eine klare ID geben,
- Typologien und Mix konsistent halten,
- eine realistische Anzahl von `Geschossen` definieren,
- nur positive Geschosshoehen verwenden,
- die Gesamtzahl der Wohneinheiten vor der Generierung pruefen.

Wenn das Programm inkonsistent ist, zeigt die Anwendung Validierungsfehler an. Der naechste Schritt sollte dann nicht erzwungen werden.

### 4. Vor der Generierung speichern

Die Generierung ist nicht als automatisches Speichern gedacht. Die korrekte Nutzung besteht darin, zuerst Grundstück und Programm zu speichern und erst danach `Entwurf generieren` auszufuehren.

Dieser Schritt aktiviert intern drei Bloecke:

1. Solver,
2. BIM-Aufbau,
3. Export.

Die Oberflaeche zeigt Phasen, Status und Fehler des Hintergrundjobs live an.

### 5. Das Ergebnis richtig interpretieren

Wenn die Generierung erfolgreich endet, wechselt das Projekt in einen machbaren oder optimalen Zustand und das Modell wird zugaenglich.

Wenn die Generierung mit einer unmachbaren Loesung endet:

- Wohneinheiten reduzieren,
- Randbedingungen lockern,
- Hoehen und Programm ueberpruefen,
- sicherstellen, dass das Grundstück ausreichend Kapazitaet hat.

Ein `infeasible`-Ergebnis sollte nicht als zufaelliger Systemfehler gelesen werden. In der Regel zeigt es einen Widerspruch in den Eingabebedingungen an.

### 6. Das IFC-Modell pruefen

Die Registerkarte `Modell` erscheint nur dann, wenn fuer die aktuelle Projektversion eine IFC-Ausgabe vorhanden ist.

Dort koennen Sie:

- den raeumlichen Modellbaum durchsuchen,
- Elemente auswaehlen,
- IFC-Eigenschaften pruefen,
- die Projektion umschalten,
- das Gesamtmodell einpassen,
- horizontale Schnitte pro Geschoss setzen,
- IFC, DXF, XLSX und SVG herunterladen.

Empfohlene Nutzung:

- zuerst die Gesamtstruktur des Gebaeudes pruefen,
- danach Geschosse und auffaellige Elemente kontrollieren,
- Baum und Eigenschaften zur Fehlerkontrolle verwenden,
- Exporte erst nach einer Mindestpruefung herunterladen.

### 7. Den konversationellen Assistenten richtig nutzen

Der `KI-Assistent` ist ein seitliches, projektbezogenes Panel. Er eignet sich fuer:

- Fragen zum Projekt,
- Erklaerungen zur erzeugten Loesung,
- Rueckfragen zu Restriktionen oder Normen,
- Vorbereitung naechster Anpassungen vor einer erneuten Bearbeitung.

Er ist nicht dazu gedacht, den geometrischen Solver zu ersetzen. Die gueltige Projektgeometrie bleibt an den deterministischen Generierungsablauf gebunden.

Wichtige Einschraenkung:

- der Chatverlauf bleibt beim Seitenwechsel nicht erhalten.

### 8. 2D-Plaene nur mit menschlicher Pruefung analysieren

Mit `Grundriss analysieren` koennen Bilddateien oder Scans eines Plans hochgeladen werden, damit Raeumlichkeiten, Labels und Symbole erkannt werden.

Dieses Modul sollte so eingesetzt werden:

- als Lesehilfe,
- als erster Entwurf,
- niemals als finale Wahrheit ohne menschliche Kontrolle.

Das Produkt weist selbst darauf hin, dass alle Ergebnisse nur naeherungsweise sind und vor einer Weiterverwendung manuell bestaetigt werden muessen.

### 9. Renderings korrekt erzeugen

Die `Rendergalerie` gehoert immer zum aktuellen Projekt. Ein Render basiert stets auf dem neuesten IFC-Modell.

Empfohlener Ablauf:

1. zuerst ein Projekt mit IFC-Ausgabe generieren,
2. die Galerie oeffnen,
3. Aussen- oder Innenansicht waehlen,
4. bei Bedarf einen deutschen Prompt ergaenzen,
5. optional ein Referenzbild hochladen,
6. den Renderjob starten und den Fortschritt beobachten.

Die UI zeigt Prozentwert, Jobstatus, letzte Ereignisse und eine geschaetzte Dauer an. Das Ergebnis wird danach in der Galerie gespeichert und in hoher Qualitaet downloadbar gemacht.

### 10. Diffusion fuer visuelle Varianten verwenden

Die Funktion `KI-Bild erstellen` dient dazu, Bilder auf Basis eines Ausgangsbildes zu erzeugen oder weiterzubearbeiten. Verfuegbar sind drei Hauptmodi:

- ControlNet mit Tiefenfuehrung,
- ControlNet mit Kantenfuehrung,
- InstructPix2Pix.

Korrekte Nutzung:

- fuer Stil-, Material- oder Atmosphaerenstudien,
- nicht als Ersatz fuer das IFC-Modell,
- immer als visuelle Ableitung und nicht als geometrische Projektmutation verstehen.

### Operative Empfehlungen

- Arbeiten Sie in dieser Reihenfolge: Grundstück, Programm, Generierung, Pruefung, Bild.
- Nutzen Sie den IFC-Viewer als Qualitaetskontrolle vor Export oder Praesentation.
- Schreiben Sie Render- und Diffusionsprompts auf Deutsch, um die Produktlogik konsistent zu halten.
- Bei Fehlern in Chat, Vision oder Diffusion zuerst Ollama, verfuegbaren GPU-Speicher und Host-Ressourcen pruefen, bevor ein Produktfehler angenommen wird.

### Wichtige Grenzen

- Der Chatverlauf bleibt nicht zwischen Seiten erhalten.
- Die Modellregisterkarte setzt eine vorhandene IFC-Datei voraus.
- Die visuelle Plananalyse erfordert zwingend menschliche Pruefung.
- Render und Diffusion sind stark hardwareabhaengig und koennen mehrere Minuten dauern.
- Generierte Bilder ersetzen nicht das validierte BIM-Modell.

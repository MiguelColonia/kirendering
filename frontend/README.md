# Cimiento Frontend

Weboberfläche für Cimiento auf Basis von React, TypeScript und Vite. Diese App ist als operative Basis für die Phase 4 aufgebaut: Projekte anlegen, Grundstück und Programm bearbeiten, Generierung auslösen und IFC-/Exportdateien abrufen.

## Stack

- React 19 + TypeScript
- Vite 8
- React Router für Navigation
- TanStack Query für Server-State
- Zustand für lokalen Entwurfszustand
- i18next mit deutscher Oberfläche
- Tailwind CSS v4 über das Vite-Plugin
- Konva als Grundlage für den 2D-Grundrisseditor
- That Open Components als Vorbereitung für IFC/3D
- `openapi-typescript` zur Ableitung von Frontend-Typen aus dem FastAPI-OpenAPI-Schema

## Starten

```bash
cd frontend
npm install
npm run dev
```

Standardmäßig erwartet die App das Backend unter `http://127.0.0.1:8000`.

Wenn die API an einer anderen Adresse läuft:

```bash
export VITE_API_BASE_URL=http://127.0.0.1:8011
npm run dev
```

## API-Typen regenerieren

Die Quelle der Wahrheit liegt im Backend. FastAPI veröffentlicht das OpenAPI-Dokument unter `/api/schemas/openapi.json`; zusätzlich bleibt `/openapi.json` als kompatibler Alias verfügbar. Das Frontend generiert daraus TypeScript-Typen in `src/types/api.generated.ts`.

Wenn das Backend bereits läuft:

```bash
cd frontend
npm run gen:types
```

Wenn Sie den gesamten Ablauf automatisiert wollen:

```bash
cd frontend
npm run sync:types
```

`sync:types` startet temporär das Backend auf Port `8000`, wartet auf das OpenAPI-Dokument, generiert die Typen und beendet den Prozess wieder. Falls bereits ein Backend auf `localhost:8000` erreichbar ist, wird dieses wiederverwendet und nicht beendet.

Regenerieren Sie die Typen immer dann, wenn sich Pydantic-Schemas, Request-/Response-Modelle oder FastAPI-Routen ändern.

## Wichtige Routen

- `/` Startseite mit Einstiegspunkten
- `/projekte` Projektliste aus der API
- `/projekte/neu` neuer Projektentwurf
- `/projekte/:projectId` Projektansicht mit Generierung und Downloads
- `/projekte/:projectId/bearbeiten` Bearbeiten einer bestehenden Projektversion

## Struktur

```text
src/
  api/                HTTP-Client und Projektendpunkte
  components/         Wiederverwendbare UI-Bausteine
  features/           Fachliche Module (Projekte, Editoren, Viewer, Generierung)
  hooks/              Reaktive Hilfslogik, z. B. WebSocket-Streams
  i18n/               Sprachinitialisierung und Übersetzungen
  pages/              Routenebenen
  types/              Generierte und abgeleitete API-Typen
  utils/              Formatierungs- und Geometriehilfen
```

## Nächste sinnvolle Schritte

1. IFC-Viewer mit echter Datei-Visualisierung an die generierte IFC-Ausgabe anbinden.
2. Formularvalidierung und Fehlermeldungen direkt aus den generierten API-Typen ableiten.
3. WebSocket-Ereignisse granularer darstellen, inklusive Builder- und Exportstatus.

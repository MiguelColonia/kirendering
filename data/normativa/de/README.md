# Normativa alemana de edificación — Fuentes PDF

Coloca aquí los PDFs de normativa alemana antes de ejecutar el script de ingesta.
Los archivos deben nombrarse con la clave del documento para que el script los reconozca automáticamente.

## Documentos soportados y dónde descargarlos

| Archivo esperado | Documento | Fuente oficial |
|---|---|---|
| `GEG.pdf` | Gebäudeenergiegesetz 2023 | [gesetze-im-internet.de/geg/](https://www.gesetze-im-internet.de/geg/) |
| `MBO.pdf` | Musterbauordnung 2016 | [is-argebau.de](https://www.is-argebau.de/verwaltungsvorschriften.aspx) |
| `LBO_Bayern.pdf` | Bayerische Bauordnung (BayBO) | [gesetze-bayern.de](https://www.gesetze-bayern.de/Content/Document/BayBO) |
| `LBO_NRW.pdf` | Bauordnung Nordrhein-Westfalen (BauO NRW 2018) | [recht.nrw.de](https://recht.nrw.de) → "Bauordnung" |
| `LBO_BW.pdf` | Landesbauordnung Baden-Württemberg (LBO BW) | [landesrecht-bw.de](https://www.landesrecht-bw.de) |
| `LBO_Hessen.pdf` | Hessische Bauordnung (HBO) | [rv.hessenrecht.hessen.de](https://rv.hessenrecht.hessen.de) |
| `BauNVO.pdf` | Baunutzungsverordnung | [gesetze-im-internet.de/baunvo/](https://www.gesetze-im-internet.de/baunvo/) |
| `WoFlV.pdf` | Wohnflächenverordnung | [gesetze-im-internet.de/woflv/](https://www.gesetze-im-internet.de/woflv/) |

## Cómo indexar

```bash
cd backend

# Verificar chunking sin escribir a Qdrant
python scripts/ingest_regulations.py --dry-run

# Indexar todos los PDFs disponibles (Qdrant y Ollama deben estar activos)
python scripts/ingest_regulations.py

# Re-indexar desde cero (elimina la colección existente)
python scripts/ingest_regulations.py --recreate

# Opciones avanzadas
python scripts/ingest_regulations.py --host qdrant-host --port 6333 --collection normativa
```

## Requisitos previos

- Qdrant activo: `docker run -p 6333:6333 qdrant/qdrant`
- Ollama activo con `nomic-embed-text` descargado: `ollama pull nomic-embed-text`
- pdfplumber instalado: incluido en las dependencias del backend

## Notas sobre los PDFs

- Los PDFs de `gesetze-im-internet.de` son de libre acceso y uso no comercial.
- Las DIN/ISO (DIN 18040, DIN 277) son normas privadas; no se redistribuyen aquí.
  Para uso profesional, descargarlas desde el Beuth Verlag o VDE Verlag con licencia válida.
- Los PDFs de LBO varían significativamente en calidad de extracción de texto.
  Los escaneados sin OCR no son compatibles con el pipeline actual; usar versiones con texto seleccionable.

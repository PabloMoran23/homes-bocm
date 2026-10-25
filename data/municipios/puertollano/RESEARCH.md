# Puertollano — investigación portal ayuntamiento

**Municipio:** Puertollano (Ciudad Real, Castilla-La Mancha)  
**INE:** 13071  
**Slug:** `puertollano`

## URLs base y semillas

| Fuente | URL | Uso |
|--------|-----|-----|
| Web corporativa | https://www.puertollano.es/ | Enlaces a sede, transparencia, departamentos |
| Sede electrónica (espublico gestiona) | https://puertollano.sedelectronica.es/ | Tablón, trámites, transparencia |
| Tablón de anuncios | https://puertollano.sedelectronica.es/board | HTML tabla + `preview-document/{uuid}` |
| Catálogo trámites | https://puertollano.sedelectronica.es/dossier | Enlaces `/catalog/t/...` (timeout frecuente en cloud) |
| Transparencia sede | https://puertollano.sedelectronica.es/transparency | Sección «7. URBANISMO…» (sin documentos indexados en scrape) |
| Datos abiertos CKAN | https://datosabiertos.puertollano.es/ | Conjunto **Obras** (CSV) |
| CSV Obras 2024 | https://datosabiertos.puertollano.es/dataset/26778018-9e2b-440c-8f84-d14d96b4ebd7/resource/76b6aec2-b147-42d0-a974-e0fbe58d3588/download/obras.csv | Expediente, coordenadas, área URBANISMO |
| Gobierno abierto | https://gobiernoabierto.puertollano.es/ | PDFs convocatoria JGL/Pleno (orden del día con asuntos URBANISMO) |
| ArcGIS JCCM planeamiento | https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0 | PGOU por `COD_INE` |

## Cómo se listan expedientes / proyectos

- **Tablón sede:** tabla HTML (`<tbody>`) con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces a PDF vía `preview-document`. La página visible suele mezclar empleo público y hacienda; los asuntos de urbanismo aparecen de forma esporádica.
- **Orden del día JGL/Pleno:** PDFs en gobierno abierto (p. ej. convocatorias con líneas `URBANISMO - LICENCIA DE OBRAS…`). No hay listado HTML scrapeable fiable desde el agente cloud (403/timeout en raíz).
- **Datos abiertos Obras:** CSV separado por `;` con `denominacion`, `expediente`, `coordenadas` (`lat, lon`), `area` (muchas filas `URBANISMO`), `direccion`, fechas de licitación/adjudicación. Es la fuente principal de filas con coordenadas.

## Licencias de obra

- No hay dataset activo de «Licencias urbanísticas» en CKAN (el grupo Urbanismo del portal de datos abiertos está vacío; el dataset fue retirado hace años).
- Las licencias concretas se anuncian en tablón y en PDFs de Junta de Gobierno / Pleno.
- El adapter incluye páginas informativas del tablón y del catálogo de trámites, más filas derivadas del CSV de obras cuando hay `expediente` y área URBANISMO.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS REST JCCM `Planeamiento_Municipal/MapServer/0`, filtro `COD_INE='13071'`, `returnGeometry=true`, `f=geojson`, `outSR=4326` → polígono del PGOU municipal (no por expediente).
  - CSV Obras: puntos `coordenadas` (lat/lon en WGS84 aproximado) sin polígono de ámbito.
- **Estrategia:** fila PGOU con `geom_geojson` desde ArcGIS; obras y tablón con `lat`/`lon` desde CSV o geocode posterior.
- **Limitaciones:** sin visor municipal por expediente; tablón sin geometría; no hay join expediente ↔ SIG municipal. El grupo CKAN Urbanismo sin datasets activos.

## Limitaciones generales

- `/dossier` puede tardar >25s o fallar en entornos cloud → catálogo de trámites opcional.
- Gobierno abierto: acceso intermitente (403) a listados; PDFs individuales accesibles por URL directa.
- Sin boletín regional asociado en cola (`bocm_count: 0`).

## Adapter

- Módulo: `municipio/adapters/puertollano.py`
- Patrón: espublico gestiona (como Piñuécar-Gandullas) + CKAN Obras + geometría PGOU (como Albacete/CLM).

# Castelló de la Plana — investigación portal ayuntamiento

Municipio: **Castelló de la Plana** (`castello-de-la-plana`) — Comunitat Valenciana, provincia Castelló. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://www.castello.es |
| Urbanismo y planificación | https://www.castello.es/es/urbanismo-y-planificacion-urbana |
| Geoportal urbanístico (info) | https://www.castello.es/es/geoportal-urbanistico |
| Visor ArcGIS | https://castelloplana.maps.arcgis.com/apps/webappviewer/index.html?id=64f1eda0cc0640e68e920ccf94c58cfc |
| Tablón de edictos (Liferay) | https://www.castello.es/buscador (assetEntryId=1535691) |
| Sede electrónica (espublico) | https://sede.castello.es |
| Tablón anuncios sede | https://sede.castello.es/board/ |
| Trámites sede | https://sede.castello.es/dossier |
| Registro autonómico OVIUS | https://ovius.gva.es/ovius-web/ |

## Cómo se listan expedientes / proyectos

1. **Geoportal Urbanístico (ArcGIS Online, org `CastelloSIG`)** — WebAppBuilder con capas del servicio `Geoportal_Urbanístico_WFL1` (FeatureServer). La capa **F. Ámbitos Planeamiento** (id 15) publica ~63 polígonos con campo `NOMBRE` (planes especiales, sectores SND, etc.) y metadatos `TIPO_`, `CATEGORIA_`. Consulta REST: `.../FeatureServer/15/query?f=geojson&outSR=4326`.
2. **Tablón sede espublico** — `/board/` lista ~10 anuncios recientes en HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_dateFrom`) con enlace `/preview-document/{uuid}`. No hay paginación pública ni histórico completo.
3. **Web Liferay** — Sección urbanismo y PDFs de anuncios BOP/DOGV en `/documents/35637/...` (p. ej. aprobaciones ED, expropiaciones). **Bloqueada en CI** (connection reset); accesible vía fetch externo/manual.
4. **OVIUS GVA** — Registro autonómico de instrumentos; SPA sin API REST scrapeable para listado masivo por municipio.

## Cómo se publican licencias

- **No hay dataset público** de licencias concedidas con dirección/coordenadas.
- La **sede espublico** expone trámites de obra/actividad vía `/dossier` (catálogo; requiere navegación JSF).
- El **tablón** publica edictos puntuales cuando hay IP/obras; en el momento de la investigación el tablón reciente no contenía filas urbanísticas.
- Estrategia del adapter: páginas informativas de sede (tablón + dossier) + scrape incremental del tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS FeatureServer `Geoportal_Urbanístico_WFL1/15` — ámbitos de planeamiento PGOU Castelló (`NOMBRE`, polígonos WGS84).
  - Capas auxiliares: clasificación (14), afecciones (18), catálogo (20), sectores C (30) — sin código de expediente enlazable.
  - ICV WFS regional (`ide.icv.gva.es`) — no resuelve en CI; datos autonómicos sin join a expediente municipal.
- **Estrategia:** Descargar polígonos de capa 15 agrupados por `NOMBRE` → `geom_geojson` en `proyectos.jsonl`. Edictos del tablón no enlazan `objectId`; sin heurística de matching por título.
- **Limitaciones:** Geometría = ámbitos del PGOU/PE, no delimitación de expedientes individuales ni licencias. `www.castello.es` inaccesible desde agente CI.

## Limitaciones generales

- Web municipal Liferay bloqueada (TCP reset) en entorno del agente; sede y ArcGIS accesibles.
- Tablón sede: solo anuncios recientes (~10 filas), sin histórico.
- Licencias: trámites informativos, sin listado de concesiones georreferenciadas.
- Duplicado en cola: `castellon-de-la-plana` (mismo municipio, ortografía alternativa).

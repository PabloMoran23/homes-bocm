# El Prat de Llobregat — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.elprat.cat | Drupal 7: urbanisme, link planejament |
| Sede electrónica (nueva) | https://seu.elprat.cat | espublico gestiona / Wicket |
| Tablón anuncios | https://seu.elprat.cat/board | Tabla HTML: expedient, procediment, categoria, PDF preview |
| Urbanisme (trámites) | https://seu.elprat.cat/citizen-service/be0ce022-2e85-4954-ae47-624e1aca3ca9 | Enlace menú sede |
| Catálogo trámites | https://seu.elprat.cat/dossier | Llicències d'obres (sin listado histórico) |
| Planejament (Drupal) | https://www.elprat.cat/link-planejament-urbanistic | Enlace a geoportal y documentación |
| Geoportal municipal | https://mapes.elprat.cat/geoportal/ | Visor enMapa (Nexus): expedients, qualificacions PGM |
| Transparencia (seu-e) | https://seu-e.cat/ca/web/elpratdellobregat/govern-obert-i-transparencia | Liferay: planejament urbanístic |
| AMB expedients GIS | geoportal.amb.cat …/Planejament/Expedients/MapServer/3 | Polígonos por expediente PGM (INE **08169**) |

### Rutas legacy `/siac/*`

Enlaces aún presentes en Drupal (`Publicaciones.aspx?t=PO`, `Tablon.aspx`, `Info.aspx?info=urbanisme`) responden **404** en la sede nueva. El adapter usa `/board` y citizen-service.

## Listado de expedientes / proyectos

- **Tablón `/board`**: filas con `class_folderCode` (núm. expediente, p. ej. `33749/2026`), categoría `Urbanisme` / `Edictes`, enlace `preview-document/{uuid}`.
- **AMB ArcGIS**: capa Expedients filtrada por `CODI_INE='08169'`; campos `NOMEXP`, `DGU`, `CMB`, geometría GeoJSON (WGS84).
- **Drupal**: pocas páginas con PDFs directos en semillas; mayoría de planeamiento vía geoportal / transparencia.

## Licencias de obra

- No hay dataset público de concesiones históricas (solo edictos en tablón cuando se publican).
- Trámites informativos: grupo «Llicències i permisos: obres» en `/dossier` (comunicación previa, obra major/menor, etc.).
- El adapter registra páginas de trámite + filas del tablón que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - AMB `Planejament/Expedients/MapServer/3` — `where=CODI_INE='08169'`, `returnGeometry=true`, `f=geojson`, `outSR=4326`
  - Geoportal municipal https://mapes.elprat.cat/geoportal/ (SPA Angular; sin API REST pública documentada en el scrape; bloqueo geográfico posible fuera de ES)
- **Estrategia:** ingestar polígonos AMB por expediente (`amb_expedients_gis`); enriquecer filas del tablón por coincidencia de título con `NOMEXP`; centroide vía `municipio.geometry`.
- **Limitaciones:** tablón muestra ~10 filas recientes (sin paginación HTML estática); geoportal municipal sin join automático por código de expediente municipal; licencias del tablón raramente llevan ref. catastral.

## Limitaciones generales

- Migración sede: URLs antiguas en la web municipal obsoletas.
- PGM compartido área metropolitana: expedientes históricos en AMB, no todos aparecen en tablón actual.
- Sin `boletin_source_id` en cola (0 entradas BOCM para este municipio).

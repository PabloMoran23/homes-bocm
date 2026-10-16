# Sancedo — investigación portal ayuntamiento

**Municipio:** Sancedo (Castilla y León, León — El Bierzo)  
**Fecha:** 2026-10-16

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica (espublico gestiona) | https://sancedo.sedelectronica.es | Portal principal (Wicket) |
| Tablón de anuncios | https://sancedo.sedelectronica.es/board | Anuncios con `preview-document` (tributos, censo electoral; sin licencias recientes) |
| Portal transparencia | https://sancedo.sedelectronica.es/transparency | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (~65 docs; carga Wicket AJAX) |
| Catálogo trámites | https://sancedo.sedelectronica.es/dossier | Trámites sede (respuesta lenta) |
| Trámite caminos rurales | https://sancedo.sedelectronica.es/citizen-service/0e2f2859-7530-423f-90f4-5d7cc7f657cb | Servicio ciudadano circulación caminos rurales |
| Web corporativa | https://www.sancedo.es | Redirección HTTP a IP (188.226.213.75); sin contenido útil scrapeable en el entorno del agente |
| PLAU CyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=24&municipio=143 | Archivo planeamiento JCyL (León, código 143) |
| PLAI CyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=24&municipio=143 | Planeamiento en información pública |
| Índice NUM | https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=301292 | Normas Urbanísticas Municipales (aprobación definitiva 27-nov-2025, BOCyL 14-ene-2026) |
| Diputación León (SAM) | https://sede.dipuleon.es/catalogoservicios.aspx?area=925 | Asistencia urbanística provincial (trámites, no listado de licencias concedidas) |

## Cómo se listan expedientes

- **PLAU CyL:** documentación oficial del planeamiento (NUM 2025/2026). Listado en PlanPublica con `openDocuIndice.do?cDocId=301292`.
- **IDECyL WFS:** geometría del instrumento NUM publicada en geoportal regional (`n_mun = 'Sancedo'`).
- **Tablón sede:** enlaces `preview-document` en HTML (tabla o extracto en `/info`); actualmente anuncios administrativos sin expedientes urbanísticos.
- **Transparencia:** sección urbanismo con decenas de documentos; navegación vía Wicket (no listado estático scrapeable).
- **Sin visor municipal** de expedientes ni API JSON de proyectos en curso.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni tablón.
- Licencias dependían históricamente de la aprobación de las NUM (noticia prensa local, ene-2026).
- Trámites vía sede electrónica y asistencia Diputación de León (SAM).
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS OWS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capa: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature NUM, plan `24143-PU-20260114-301292`)
  - Capas sectores/parciales: 0 features para Sancedo
  - Filtro: `n_mun = 'Sancedo'`
  - Documentación: `url_doc_info` → PlanPublica `cDocId=301292`
- **Estrategia:** ingestar feature WFS con `geom_geojson` (MultiPolygon WGS84); enriquecer entradas PLAU/tablon por coincidencia de título con NUM.
- **Validación geográfica:** IGN no devuelve límite exacto «Sancedo»; el manifest usa el ámbito NUM WFS como `municipal_boundary` (OSM admin relation como respaldo documentado en `osm_municipal_boundary.json`).
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente individual → geometría.
  - Licencias de obra sin georreferencia pública.
  - Transparencia urbanismo no scrapeable sin sesión AJAX.
  - Web municipal inestable (redirect IP).

## Limitaciones generales

- Tablón sede sin licencias ni planeamiento reciente en anuncios.
- BOCyL ya en pipeline regional (`bocyl`, 1 entrada).
- `/dossier` puede tardar >60s; catálogo opcional en ingest.

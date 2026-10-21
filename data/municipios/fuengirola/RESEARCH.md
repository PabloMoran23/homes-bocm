# Fuengirola — investigación portal ayuntamiento

Municipio: **Fuengirola** (`fuengirola`), provincia de Málaga, Andalucía.

## URLs base y semillas

| Recurso | URL | Formato |
|---------|-----|---------|
| Web municipal | https://www.fuengirola.es | WordPress |
| Concejalía Urbanismo | https://www.fuengirola.es/concejalia/concejalia-de-urbanismo/ | HTML informativo |
| Sede electrónica (home) | https://sede.fuengirola.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME | STA TAO |
| Tablón anuncios/edictos | https://sede.fuengirola.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | HTML + `dataset_PTS2_TABLON` JSON embebido (~401 filas) |
| Catálogo trámites | https://sede.fuengirola.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV` embebido |
| Expedientes de planeamiento (docs) | https://sede.fuengirola.es/sta/Relec/CatalogDetail?action=info&dboidProcedure=6262631033864740205304&dboidRequest=6269031114319068205304 | HTML + enlaces `GetDocumentServlet` (~72 PDFs) |

Detalle tablón: `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.

## Listado de expedientes / proyectos

1. **Tablón STA:** array JavaScript `var dataset_PTS2_TABLON = [...]` con `descriptionProc`, `externString`, `pubDateIni`, `remitent`, `dboid`. Filtro por keywords urbanísticas en título/remitente (~70+ entradas relevantes).
2. **Trámite «Expedientes de Planeamiento» (EXP_PLAN):** documentación relacionada en tabla con PDFs descargables vía `/sta/docs/GetDocumentServlet?CUD=...&HASH_CUD=...` (estudios de detalle TB-52, SUNCOT-02, SUNC-14, convenios, etc.).
3. **PGOU:** aprobación definitiva 2011 (BOJA); no hay visor municipal público con capas enlazadas al expediente en la web investigada.

## Licencias de obra

- **Tablón:** anuncios de licencias, comunicaciones previas y disciplina urbanística cuando se publican.
- **Catálogo:** trámites «Licencia de Obra Mayor», «Comunicación Previa Inicio Obras», declaraciones responsables, etc. — páginas informativas (no listado de concesiones con coordenadas).
- No hay dataset abierto de licencias georreferenciadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Noticias ayuntamiento sobre GIS Esri (planeamiento/callejero/catastro) sin URL de visor o REST público enlazado desde la sede.
  - `https://geagis.gestagua.es/arcgis/rest/services/FUENGIROLA` — servicios de abastecimiento/saneamiento/sectorización (Gestagua), no planeamiento ni expedientes.
- **Estrategia:** el adapter no rellena `geom_geojson`; el orquestador usa centroide municipal (`manifest.portal.config.centroid`) + jitter en geocode.
- **Limitaciones:** tablón y catálogo solo metadatos/PDF; sin WFS/ArcGIS municipal con código de expediente.

## Limitaciones generales

- Tablón completo (`KEY=all`) ~580 KB HTML; timeout recomendado ≥90 s.
- Codificación de `CatalogDetail` a veces ISO-8859-1 (fallback `latin-1` en fetch).
- Muchos anuncios del tablón son no urbanísticos (personal, ordenanzas generales); filtros regex en adapter.

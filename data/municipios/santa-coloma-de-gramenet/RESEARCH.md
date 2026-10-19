# Santa Coloma de Gramenet — investigación portal

## Web oficial

- **Base:** https://www.gramenet.cat
- **Planeamiento / información urbanística:** https://www.gramenet.cat/es/ayuntamiento/areas-municipales/planeamiento-urbanistico-informacion-urbanistica/
- **Expedientes urbanísticos (índice):** …/expedientes-urbanisticos/
  - Subsecciones: planes urbanísticos (territoriales, generales, derivados), estudios de detalle, convenios, ordenaciones volumétricas, otros.
- **Expedientes en trámite:** …/expedientes-en-tramite/
- **Gestión urbanística:** …/gestion-urbanistica/
- **Licencias y disciplina:** https://www.gramenet.cat/es/ayuntamiento/areas-municipales/licencias-y-disciplina-urbanistica/
- **Sede:** https://www.gramenet.cat/es/sede-electronica/ (instancia genérica, cita previa “Obras y Actividades comerciales”)

## Cómo se listan expedientes

- **CMS:** TYPO3 (Bootstrap Package + extensión municipal `theme_sc`).
- **Listados:** páginas estáticas con enlaces a fichas por expediente (slug en URL); planes derivados con decenas de PERI/planes especiales enlazados.
- **No hay** API JSON pública en el listado HTML; los metadatos estructurados están en **GeoServer WFS** (véase geometría).
- Documentación complementaria en PDFs bajo `/fileadmin/Files/Ajuntament/informacio_urb/`.

## Licencias de obra

- **No** hay tablón de anuncios ni dataset de concesiones de licencias en la web del ayuntamiento.
- Trámites presenciales / cita previa OIAC y sede (instancia genérica, FUE para actividades).
- El adapter ingiere **páginas informativas** de trámites (patrón Pozuelo), no concesiones.

## Geometría / visor

- **geometry_status:** `available`
- **Visor:** https://www.gramenet.cat/geoportal/ (Angular + OpenLayers, Nexus Geographics).
- **Config visor:** https://www.gramenet.cat/geoportal/assets/applicationProperties/config.json
  - SRS mapa: `EPSG:25831`
  - Servicio WMS/WFS municipal: `https://www.gramenet.cat/geoserver/gramenetgis/wms?`
- **Fuentes WFS (polígonos expedientes):**
  - Aprobados: `gramenetgis:eu_expurb_vigents_pu|ed|cu|gu|ov`
  - Gestión: `gramenetgis:gu_exp_gestio`
  - En trámite: `gramenetgis:eu_plansurb_tramit`, `eu_estudidetall_tramit`, `eu_conveniurb_tramit`, `eu_ordvolums_tramit`, `gu_exp_gestio_tram`, `eu_suspllic_tramit`
- **Campos enlace:** `exp_cod_aj`, `exp_nom`, `exp_daprov`, `exp_link`, geometría `MultiPolygon` en `EPSG:4326` vía `srsName=EPSG:4326`.
- **Estrategia adapter:** `GetFeature` paginado por capa; filas web TYPO3 enriquecidas por código/título/URL.
- **Limitaciones:** capas `_txt` son puntos/etiquetas (no usadas); visor interactivo sin REST ArcGIS documentado; licencias sin georreferencia.

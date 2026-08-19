# Arenas de San Pedro — investigación portal ayuntamiento

**Municipio:** Arenas de San Pedro (Castilla y León, Ávila)  
**Fecha:** 2026-08-12

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress Avada) | https://arenasdesanpedro.es | Portal activo |
| Urbanismo, Obras y Servicios | https://arenasdesanpedro.es/concejalias/urbanismo-obras-y-servicios/ | Concejalía, áreas de actuación |
| Solicitudes / formularios PDF | https://arenasdesanpedro.es/concejalias/urbanismo-obras-y-servicios/solicitudes/ | Licencias, declaraciones responsables, comunicaciones |
| ITE | https://arenasdesanpedro.es/concejalias/urbanismo-obras-y-servicios/inspeccion-tecnica-de-edificios/ | Información ITE |
| Sede electrónica (espublico gestiona) | https://arenasdesanpedro.sedelectronica.es/board | Tablón de anuncios (~10 filas visibles) |
| Sede catálogo | https://arenasdesanpedro.sedelectronica.es/catalog | Trámites electrónicos |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=05&municipio=014 | Sin documentos listados en búsqueda pública |
| WP REST API | https://arenasdesanpedro.es/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** páginas de concejalía con PDFs de solicitudes en `/wp-content/uploads/`. REST API `wp/v2/pages` y `wp/v2/posts` (noticias de obras municipales en calles, etc.).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Mezcla anuncios de empleo, presupuesto y acceso a información pública.
- **PLAI:** municipio código 014 (provincia 05 Ávila); búsqueda pública sin filas de documentos scrapeables (planeamiento referenciado vía IDECyL WFS).
- **Sin visor municipal** de expedientes urbanísticos ni API JSON histórica en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Formularios PDF en web: licencia obra mayor, declaración responsable, comunicación ambiental, cambio titularidad.
- Tablón puede incluir autorizaciones (ferias, barras) pero no concesiones sistemáticas de licencias de obra.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia/autorización.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Arenas de San Pedro'`
  - 1 instrumento (NNSS), 24 sectores, 2 planes parciales (Ramacastañas PP-7A, Las Moyas) con polígonos MultiPolygon
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector (Ramacastañas, etc.) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo anuncios recientes; `/info` responde lento o vacío.
  - Certificado sede requiere `insecure_ssl` en algunos entornos (timeout con verificación estricta).
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Municipio ~650 hab. en núcleo principal; incluye pedanías (Ramacastañas, La Parra, etc.).
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 4 entradas en CSV).
- Volumen bajo de publicaciones urbanísticas activas en tablón.

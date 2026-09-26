# Casavieja — investigación portal ayuntamiento

**Municipio:** Casavieja (Castilla y León, Ávila)  
**Fecha:** 2026-08-26

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://ayuntamientodecasavieja.es | Portal activo (Business+ Media, PHP 8.3) |
| Urbanismo | https://ayuntamientodecasavieja.es/urbanismo/ | Enlaces a normativa JCyl, trámites sede y PlanPublica |
| Plano urbanístico | https://ayuntamientodecasavieja.es/plano/ | Plano municipal |
| Bandos y anuncios | https://ayuntamientodecasavieja.es/bandos-y-anuncios/ | Anuncios municipales (autorización desescombro, etc.) |
| PlanPublica JCyl | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=054 | Documentación planeamiento publicada |
| Sede electrónica (espublico gestiona) | https://casavieja.sedelectronica.es/board | Tablón de anuncios (3 filas visibles) |
| Transparencia sede | https://casavieja.sedelectronica.es/transparency | Sin documentos preview visibles |
| WP REST API | https://ayuntamientodecasavieja.es/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** páginas estáticas de urbanismo con enlaces externos a JCyl y sede. REST API `wp/v2/pages` y `wp/v2/posts` (noticias con autorizaciones urbanísticas).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Incluye `Licencias Urbanísticas` (p. ej. expediente 117/2022 renovación LAAT).
- **PlanPublica:** catálogo regional de documentos de planeamiento (provincia 05, municipio 054).
- **Sin visor de expedientes** ni API JSON de listado histórico completo en sede.
- Rutas `/dossier.*` y `/info.0` de la sede devuelven bucle de redirección 302 (no scrapeables).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón muestra anuncios de licencias urbanísticas (infraestructura eléctrica) y trámites genéricos.
- Trámites en sede enlazados desde urbanismo (`dossier.61`, `dossier.4`) no accesibles por redirect loop.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Casavieja'` (c_mun `05054`)
  - 1 instrumento (Normas Subsidiarias de Planeamiento Municipal 1994) + 14 sectores con polígono
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (sin archivo scrapeable).
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Sede `/dossier.*` e `/info.0` con bucle de redirección; tablón `/board` accesible.
- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~900 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).

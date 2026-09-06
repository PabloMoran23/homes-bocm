# Almazán — investigación portal ayuntamiento

**Municipio:** Almazán (Castilla y León, Soria)  
**INE:** 42006 (c_mun WFS: 42020)  
**Fecha:** 2026-09-06

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://almazan.es | Portal activo (Yoast SEO, tema municipal) |
| PGOU | https://almazan.es/informacion-municipal/normativa-municipal/plan-general-de-ordenacion-urbana-de-almazan/ | ~180 PDFs del PGOU (memorias, planos, normas) |
| Normativa municipal | https://almazan.es/informacion-municipal/normativa-municipal/ | Ordenanzas y enlaces urbanísticos |
| Instancias / licencias | https://almazan.es/informacion-municipal/instancias/ | Modelos PDF: licencia obra mayor, ambiental, declaración responsable |
| Sede electrónica (espublico gestiona) | https://almazan.sedelectronica.es/board/ | Tablón de anuncios (~3 filas visibles) |
| Trámites sede | https://almazan.sedelectronica.es/dossier | Catálogo de trámites (redirect loop sin sesión; board accesible) |
| PLAU JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=006 | 8+ documentos (NUM, estudio de detalle) |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=006 | Información pública planeamiento |
| WP REST API | https://almazan.es/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** páginas estáticas con cientos de PDFs del PGOU en `/wp-content/uploads/`. REST API `wp/v2/pages` y `wp/v2/posts`.
- **PGOU:** documentación completa del Plan General (memorias, planos, normas) publicada como PDFs descargables.
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Incluye información pública de proyectos (autorización ambiental hidrógeno/metanol verde, jul 2026).
- **PLAU JCYL:** tabla HTML con documentos de planeamiento aprobado (NUM, modificaciones, estudio de detalle).
- **IDECyL WFS:** 42 features (1 instrumento, 2 planes parciales, 39 sectores) con geometría en EPSG:4326.
- **Sin visor de expedientes** municipal ni API JSON de listado histórico completo en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón actual muestra principalmente ordenanzas y anuncios generales; ocasionalmente información pública de proyectos.
- Modelos en web (instancias): solicitud licencia obra mayor, licencia ambiental, declaración responsable obra menor.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia o urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (2), `urbanismo:plau_cyl_sectores` (39)
  - Filtro: `n_mun = 'Almazán'` (c_mun `42020`, provincia Soria)
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón/PLAU por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Planos PDF del PGOU sin coords embebidas.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (sin archivo scrapeable).
  - `/dossier` e `/info` de sede devuelven redirect loop sin cookies de sesión.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio soriano (~5.500 hab.); volumen moderado de publicaciones urbanísticas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).

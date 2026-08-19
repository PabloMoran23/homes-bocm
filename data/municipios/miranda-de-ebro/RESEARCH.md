# Miranda de Ebro — investigación portal ayuntamiento

**Municipio:** Miranda de Ebro (Castilla y León, Burgos)  
**Fecha:** 2026-08-13

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress + Astra/Elementor) | https://www.mirandadeebro.es | Portal activo |
| Área de Urbanismo | https://www.mirandadeebro.es/ayuntamiento/servicios/area-de-urbanismo/ | ARU, ERRP, planes, mapa ruido |
| ARU | https://www.mirandadeebro.es/ayuntamiento/servicios/area-de-urbanismo/a-r-u/ | PDF plano ARU, planeamientos aprobados |
| ERRP | https://www.mirandadeebro.es/ayuntamiento/servicios/area-de-urbanismo/e-r-r-p/ | Entorno Ebro Entrevías |
| Planes urbanísticos (tipo doc.) | https://www.mirandadeebro.es/tipo-documentacion/planes-urbanisticos/ | Documentación planeamiento |
| Transparencia ordenación urbana | https://www.mirandadeebro.es/transparencia/urbanismo-obras-publicas-y-medio-ambiente/ordenacion-urbana/ | Enlaces a urbanismo |
| Documentación / trámites | https://www.mirandadeebro.es/documentacion/ | Licencias obra, cédula, parcelación, etc. |
| Archivo planeamiento | https://www.mirandadeebro.es/documentacion/archivo-de-planeamiento-urbanistico/ | Referencia archivo municipal |
| Sede electrónica (STA) | https://sede.mirandadeebro.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON | Tablón anuncios y edictos |
| Catálogo trámites sede | https://sede.mirandadeebro.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | Filtro departamento Urbanismo |
| Junta CYL info pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=219 | Planeamiento en información pública |
| Junta CYL archivo aprobado | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=219 | Planeamiento aprobado |
| WP REST API | https://www.mirandadeebro.es/wp-json/wp/v2/documentacion | Trámites y documentación |

## Cómo se listan expedientes

- **WordPress:** páginas de urbanismo con PDFs (`/wp-content/uploads/`, `/PDFS/`). REST API `wp/v2/documentacion` (trámites y documentos).
- **Sede STA:** tablón con dataset JavaScript embebido `dataset_PTS2_TABLON` (patrón Aranda/Segovia). Catálogo con `dataset_CATSERV` filtrado por keyword urbanismo `PTS_PC_012`.
- **IDECyL WFS:** catálogo regional PLAU CyL con sectores e instrumentos del municipio (`c_mun=09219`).
- **Junta CYL PlanPublica:** visor web de instrumentos y documentos (sin API JSON directa).
- No hay visor municipal ArcGIS de expedientes individuales enlazado al listado.

## Cómo se publican licencias

- No hay dataset histórico abierto de concesiones de licencia (como Madrid datos abiertos).
- Tablón sede puede incluir anuncios de licencias/urbanismo cuando accesible.
- Trámites informativos en web: licencia obra mayor/menor, primera ocupación, comunicación ambiental, cédula urbanística, parcelación, ocupación vía pública.
- Estrategia adapter: páginas informativas de trámites + catálogo sede + tablón si accesible.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (12), `urbanismo:plau_cyl_sectores` (73)
  - Filtro: `n_mun = 'Miranda de Ebro'`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_titulo`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría individual.
  - Licencias de obra sin georreferencia pública.
  - Sede `sede.mirandadeebro.es` puede rechazar conexiones TLS desde algunos entornos (reset en handshake); tablón no scrapeable en cloud agent.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 4 entradas en CSV).
- Municipio medio (~36.000 hab.); volumen moderado de planeamiento en IDECyL.
- Web nueva (2024) con rutas legacy `/Miranda/Ayuntamiento/...` en algunos enlaces ARU.

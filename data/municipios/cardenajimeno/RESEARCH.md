# Cardeñajimeno — investigación portal ayuntamiento

**Municipio:** Cardeñajimeno (Castilla y León, Burgos)  
**Fecha:** 2026-08-26

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Drupal 10 Toools) | https://cardenajimeno.es | Portal activo (Diputación Burgos) |
| Normativa | https://cardenajimeno.es/normativa | Enlaces sede y normativa general |
| Noticias | https://cardenajimeno.es/noticias | Avisos (A-12, DUS alumbrado, etc.) |
| Sede electrónica (espublico gestiona) | https://cardenajimeno.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://cardenajimeno.sedelectronica.es/board | Tabla HTML con `preview-document` |
| Portal transparencia | https://cardenajimeno.sedelectronica.es/transparency | 23 docs en «Urbanismo, obras públicas y medio ambiente» |
| Catálogo trámites | https://cardenajimeno.sedelectronica.es/dossier | Trámites on-line (Wicket) |
| PlanPublica PLAU (archivo aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=074 | ~14 instrumentos (NS, PP SUB-*, PAU, ED, PN) |
| PlanPublica PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=074 | Sin expedientes en curso al scrape |
| Archivo JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09074 | Índice planeamiento municipal |

## Cómo se listan expedientes

- **PlanPublica JCyL:** tabla HTML con instrumentos aprobados (NS 1994, modificaciones, planes parciales SUB-4/5/6, PAU Parque Tecnológico Burgos, estudios de detalle).
- **IDECyL WFS:** sectores y ámbito NUM con geometría (`n_mun = 'Cardeñajimeno'`, `c_mun = 09074`).
- **Tablón sede:** HTML espublico; actualmente ~1 anuncio (inmatriculación finca polígono 6).
- **Transparencia sede:** categoría «Urbanismo, obras públicas y medio ambiente» con PDFs históricos.
- **Web Drupal:** sin sección urbanismo dedicada; noticias mezcladas (infraestructura, cultura).

## Cómo se publican licencias

- No hay dataset abierto de concesiones de licencia de obra.
- Trámites presenciales / sede electrónica sin listado histórico público scrapeable.
- Estrategia adapter: páginas informativas (normativa, transparencia, dossier) + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM), `urbanismo:plau_cyl_sectores` (13), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'Cardeñajimeno'`
  - Campos: `n_sector`, `n_num_sect`, `n_titulo`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PlanPublica/tablón por código de sector (`SUB-4`, `SUB-6`, etc.) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría individual.
  - Licencias sin georreferencia.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no licencias.

## Limitaciones generales

- Tablón sede con pocos anuncios recientes.
- Catálogo `/dossier` puede responder lento; adapter prioriza PlanPublica + WFS.
- BOCyL ya parseado en pipeline regional (`bocyl`, 2 entradas).

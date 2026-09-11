# Cardeñosa — investigación portal ayuntamiento

**Municipio:** Cardeñosa (Castilla y León, Ávila)  
**Fecha:** 2026-09-11

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Dip. Ávila CMS) | https://www.cardenosa.es | Portal activo, plantilla Diputación de Ávila 2020 |
| Normas urbanísticas | https://www.cardenosa.es/ayuntamiento/normas-urbanisticas/ | NNSS revisión 2025, catálogo, planos PDF |
| Tablón de anuncios | https://www.cardenosa.es/ayuntamiento/tablon-de-anuncios/ | Anuncios municipales (subastas solares, etc.) |
| Anuncios boletines | https://www.cardenosa.es/ayuntamiento/anuncios-boletines/ | Publicaciones BOCYL |
| Bandos | https://www.cardenosa.es/ayuntamiento/bandos/ | Bandos municipales |
| RSS 2.0 | https://www.cardenosa.es/rss.xml | Feed de noticias y anuncios |
| Sede electrónica (espublico gestiona) | https://cardenosa.sedelectronica.es/board | Tablón sede (~2 anuncios recientes) |
| Sede info pública | https://cardenosa.sedelectronica.es/info | Tablón información pública |
| PLAU JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=049 | Planeamiento vigente (c_mun 05049) |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=05&municipio=049 | Información pública planeamiento |

## Cómo se listan expedientes

- **CMS Dip. Ávila:** fichas HTML en `/ayuntamiento/<sección>/<slug>.html` con documentos PDF en `/docus/ayuntamiento/<año>/`. Listados por sección con tarjetas `div.fch`.
- **RSS:** canal global con título, enlace y fecha de publicación.
- **Tablón web:** anuncios en sección `tablon-de-anuncios` (subasta solares Santa Paula 2025, etc.).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Pocas filas activas (bicicletas, incendios).
- **PLAU JCYL:** documentos de planeamiento indexados por provincia 05 / municipio 049.
- **Sin visor municipal** de expedientes urbanísticos ni API JSON en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Trámites urbanísticos vía sede electrónica (catálogo no indexado públicamente en HTML estático).
- Tablón web/sede sin licencias de obra publicadas sistemáticamente.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia/autorización.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Cardeñosa'` (c_mun `05049`)
  - 1 instrumento (NNSS revisión 2025), 30 sectores con polígonos MultiPolygon
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas web/tablón por coincidencia de nombre en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - PDFs de planos en web sin coordenadas embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Municipio ~500 hab.; patrimonio arqueológico (Castro de las Cogotas).
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
- Sede `/info` puede responder lento; requiere `insecure_ssl` en algunos entornos.
- Página `/sede-electronica/` del CMS a veces con timeout elevado.

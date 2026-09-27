# Padiernos — investigación portal ayuntamiento

**Municipio:** Padiernos (Castilla y León, Ávila)  
**Fecha:** 2026-09-27

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Dip. Ávila CMS) | https://www.padiernos.es | Portal activo, plantilla Diputación de Ávila 2020 |
| Normas urbanísticas | https://www.padiernos.es/ayuntamiento/normas-urbanisticas/ | Enlace PLAU JCYL, normas vigentes |
| Tablón de anuncios | https://www.padiernos.es/ayuntamiento/tablon-de-anuncios/ | Anuncios municipales |
| Anuncios boletines | https://www.padiernos.es/ayuntamiento/anuncios-boletines/ | Publicaciones BOCYL |
| Bandos | https://www.padiernos.es/ayuntamiento/bandos/ | Bandos municipales |
| RSS 2.0 | https://www.padiernos.es/rss.xml | Feed de noticias y anuncios |
| Sede electrónica (espublico gestiona) | https://padiernos.sedelectronica.es/board | Tablón sede |
| Sede info pública | https://padiernos.sedelectronica.es/info | Tablón información pública |
| PLAU JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=176 | Planeamiento vigente (c_mun 05176) |

## Cómo se listan expedientes

- **CMS Dip. Ávila:** fichas HTML en `/ayuntamiento/<sección>/<slug>.html` con documentos PDF en `/docus/ayuntamiento/<año>/`. Listados por sección con tarjetas `div.fch`.
- **RSS:** canal global con título, enlace y fecha de publicación.
- **Tablón web:** sección `tablon-de-anuncios`.
- **Tablón sede:** HTML tabla espublico con `preview-document`.
- **PLAU JCYL:** documentos de planeamiento indexados por provincia 05 / municipio 176.
- **Sin visor municipal** de expedientes urbanísticos ni API JSON en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Trámites urbanísticos vía sede electrónica (catálogo espublico).
- Tablón web/sede sin licencias de obra publicadas sistemáticamente.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia/autorización.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Padiernos'` (c_mun `05176`)
  - Sectores PLAU (p. ej. UA.1) con polígonos
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas web/tablón por coincidencia de nombre en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - PDFs de planos en web sin coordenadas embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Municipio ~277 hab.; a 14 km de Ávila capital.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
- Sede puede requerir `insecure_ssl` en algunos entornos cloud.

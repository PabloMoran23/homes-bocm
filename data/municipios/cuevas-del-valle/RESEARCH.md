# Cuevas del Valle — investigación portal ayuntamiento

**Municipio:** Cuevas del Valle (Castilla y León, Ávila)  
**Fecha:** 2026-09-13

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.cuevasdelvalle.es | CMS estático DipuÁvila 2020 |
| Normas urbanísticas | https://www.cuevasdelvalle.es/ayuntamiento/normas-urbanisticas/ | 4 fichas (modificaciones puntuales NN.SS, enlace PLAU) |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=066 | 12 documentos de planeamiento vigente (cód. municipio 066) |
| Sede electrónica (espublico gestiona) | https://cuevasdelvalle.sedelectronica.es/board | Tablón de anuncios |
| Sede trámites | https://cuevasdelvalle.sedelectronica.es/dossier | Catálogo de trámites |
| Sede inicio | https://cuevasdelvalle.sedelectronica.es/info.0 | Redirige desde raíz |

## Cómo se listan expedientes

- **Web DipuÁvila:** listado HTML en `/ayuntamiento/normas-urbanisticas/` con bloques `<div class="fch" data-ids="...">` → artículo con `<h1>`, `<time datetime>`, enlace a `.html` de detalle.
- **PLAU CyL:** tabla HTML pública por código provincia/municipio (05/066); enlaces `openDocumento.do?cDocId=...`.
- **Tablón sede:** HTML espublico estándar (`preview-document`); pocas filas (ordenanzas, no urbanismo).
- **Sin visor de expedientes** ni listado JSON de IP en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Trámites de licencia disponibles en catálogo sede (espublico); sin listado público de concesiones.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios de urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Cuevas del Valle'`
  - Resultado: 1 instrumento (NNSS) + 8 sectores (UE-1…UE-7, S.A.U. El Rebollar) con `MultiPolygon`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer fichas web/PLAU por coincidencia de sector (UE-3, El Rebollar, Las Cerquitas, etc.) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia en portal.
  - Tablón sede sin anuncios de licencias urbanísticas.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier` responde lento; `/board` accesible con pocas filas no urbanísticas.
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).

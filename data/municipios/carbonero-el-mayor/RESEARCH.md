# Carbonero el Mayor — investigación portal ayuntamiento

**Municipio:** Carbonero el Mayor (Castilla y León, Segovia)  
**Fecha:** 2026-09-11

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Joomla 1.5) | https://carboneroelmayor.es | Portal municipal clásico |
| Urbanismo | https://carboneroelmayor.es/index.php?option=com_content&view=section&id=8&layout=blog&Itemid=81 | NUM (texto refundido 2012), modificaciones puntuales 1-13/2-13/3-13, M.P. 2014, mapa ruido, noticias |
| Sede electrónica | https://carboneroelmayor.sedelectronica.es | Plataforma **espublico gestiona** |
| Tablón sede | https://carboneroelmayor.sedelectronica.es/board | Anuncios con `preview-document/…` (estudio de detalle 2-2025, información pública expediente 240/2026, etc.) |
| PLAI JCYL (prov. 40, mun. 049) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=049 | Archivo planeamiento aprobado |
| PLAI info pública | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=049 | Planeamiento en tramitación |

## Cómo se listan expedientes

- **Joomla sección urbanismo:** blog con enlaces directos a PDFs en `/images/stories/documentos/` (NUM, modificaciones puntuales, mapa ruido) y artículos de noticias.
- **Tablón espublico:** tabla HTML con filas `preview-document/…` (Wicket). Categorías «Urbanismo» y «Licencias Urbanísticas».
- **PLAI JCYL:** tabla HTML paginada con documentos de planeamiento (provincia 40, municipio 049).
- Sin visor de expedientes ni API JSON pública.

## Cómo se publican licencias

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); requieren certificado para iniciar.
- Tablón publica anuncios urbanísticos (estudios de detalle, información pública) pero no listado histórico de concesiones con coordenadas.
- Estrategia adapter: tablón sede + páginas informativas de trámites + formularios en web Joomla.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM), `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores` (19 sectores: S.1–S.9, S.A–S.G, S7A/S7B, etc.)
  - Filtro: `n_mun = 'Carbonero el Mayor'`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `f_aprob`, `f_bocyl`
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de sector/código en títulos de tablón, Joomla y PLAI.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→polígono individual.
  - Licencias de obra sin georreferencia en tablón.
  - PDFs de normativa sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Joomla 1.5 antiguo; paginación manual en sección urbanismo.
- Sede `/dossier` puede responder lento desde CI; el adapter tolera fallo.
- Sin API JSON; scrape determinista HTML + WFS + PLAI.
- 1 entrada BOCYL en CSV regional (`boletin_source_id: bocyl`).

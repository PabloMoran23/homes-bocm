# Valdeavellano de Tera — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `valdeavellano-de-tera` |
| Provincia | Soria (42) |
| CCAA | Castilla y León |
| Boletín | BOCYL (`boletin_source_id: bocyl`) |
| Código INE | 42191 |
| Población | ~220 hab. |

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://www.valdeavellanodetera.es | Drupal 7 (bootstrap_subtheme) |
| Sede electrónica | https://valdeavellanodetera.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://valdeavellanodetera.sedelectronica.es/board | HTML tabla + preview-document |
| Catálogo trámites | https://valdeavellanodetera.sedelectronica.es/dossier | HTML enlaces `/catalog/t/...` |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=42&municipio=206 | HTML paginado |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | GeoJSON WFS 2.0 |
| Perfil contratante | http://municipio.dipsoria.es/cgi-vel/perfil-c-valdeavellano/index.pro | Liferay DipSoria |

### Páginas Drupal relevantes

- `/modificacion-no-12-de-las-normas-urbanisticas-municipales` — modificación Nº 12 NNSS (node/9594)
- `/informacion-municipal` — enlaces a sede y transparencia
- `/ayuntamiento` — corporación y enlaces institucionales

## Cómo se listan expedientes / proyectos

1. **PLAI JCYL** (principal): publicaciones de planeamiento (NUT, modificaciones) con `doOpen(docId)` → PDF descargable. Código municipio PLAI: `42191` (provincia 42, municipio 206).
2. **IDECyL WFS**: 7 polígonos (1 instrumento ámbito NUT, 6 sectores) con campos `c_id_sect` (`42191UA.1`–`42191UA.5`, `42191SURD.so.1`).
3. **Drupal**: noticias de modificaciones urbanísticas y PDFs embebidos en `/sites/valdeavellanodetera.es/files/...`.
4. **Tablón sede**: avisos administrativos (IAE, incendios, etc.); sin licencias urbanísticas publicadas actualmente.
5. **BOCM/BOCYL**: 2 entradas históricas (modificaciones NNSS, estudio de detalle calle Molinillo nº22).

## Cómo se publican licencias

- **Tablón**: sin licencias de obra publicadas en el momento de la investigación.
- **Trámites sede**: catálogo incluye trámites de urbanismo y licencias — páginas informativas, no concesiones.
- El adapter devuelve páginas de trámite informativas (patrón Pozuelo/Langa de Duero).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 6 sectores con polígono WGS84
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono ámbito NUT
  - Filtro: `CQL_FILTER=n_mun='Valdeavellano de Tera'`
  - Campos enlace: `c_id_sect`, `n_sector`, `url_doc_info`
- **Estrategia:** descarga WFS por capa; enriquecimiento por coincidencia de título/sector en filas PLAI y Drupal; sectores conocidos: `42191UA.*`, `42191SURD.so.1`.
- **Limitaciones:**
  - No hay visor ArcGIS propio del ayuntamiento.
  - Licencias del tablón no llevan geometría (solo PDFs administrativos).
  - Sede electrónica requiere `insecure_ssl: true` (certificado rechazado por algunos clientes TLS estrictos).
  - PLAI no expone geometría; solo documentos PDF.
  - Sectores WFS sin nombre descriptivo (`n_sector` = «No asignado»).

## Limitaciones generales

- Portal Drupal 7 con poco contenido urbanístico activo en la web.
- Tablón sede con publicaciones administrativas generales.
- Sin API JSON pública; scrape HTML determinista.
- Sin licencias de obra con coordenadas publicadas.

## Referencias técnicas

- Adapter patrón: `langa_de_duero.py` (misma provincia/CCAA, PLAI+WFS+espublico).
- Código PLAI: provincia `42`, municipio `206` (prefijo expedientes `42191`).

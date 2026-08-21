# Ólvega — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `olvega` |
| Provincia | Soria (Castilla y León) |
| Web corporativa | https://www.olvega.es (Drupal 7 + Bootstrap) |
| Sede electrónica | https://olvega.sedelectronica.es (espublico gestiona) |
| Boletín | BOCYL (`bocyl`) — 3 entradas en CSV |

## URLs base y páginas semilla

### Web corporativa (Drupal 7)

- Inicio: https://www.olvega.es/
- Tablón de edictos: https://www.olvega.es/tablon-de-edictos
- Trámites licencias (informativos): `/solicitud-licencia-de-obras-con-proyecto`, `/solicitud-licencia-de-obras-sin-proyecto`
- Normas urbanísticas / modificaciones puntuales: `/modificacion-puntual-v-de-las-normas-urbanisticas-municipales`, `/modificacion-puntual-vi-normas-urbanisticas-municipales`, `/edicto-modificacion-puntual-vii-de-las-normas-urbanisticas`
- Estudios de detalle / IP: `/edicto-estudio-de-detalle-s-l-1`, `/actualidad/anuncio-de-informacion-publica-*`
- PDFs en `/sites/olvega.es/files/public/...`

### Sede electrónica (espublico)

- Tablón de anuncios: https://olvega.sedelectronica.es/board (~10 filas visibles)
- Información pública: https://olvega.sedelectronica.es/info
- Catálogo de trámites: https://olvega.sedelectronica.es/dossier
- Consulta expedientes: https://olvega.sedelectronica.es/expedientes
- Documentos vía `preview-document/{uuid}`

### PLAI JCYL (planeamiento)

- Buscador: https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do
- Parámetros: `provincia=42`, `municipio=134` (código PLAI Ólvega)
- ~15+ documentos: NUM, PP, PPI, ED (modificaciones puntuales, planes parciales sectores III/IV/SI-3, estudios de detalle)

## Cómo se listan expedientes

| Fuente | Formato | Contenido urbanístico |
|--------|---------|----------------------|
| Drupal tablón/edictos | HTML + PDFs enlazados | Modificaciones NUM, estudios de detalle, IP licencias |
| Sede `/board` | Tabla HTML (Wicket) | Urbanismo, licencias urbanísticas, información pública |
| PLAI JCYL | HTML tabla paginada | Instrumentos de planeamiento (NUM, PP, ED) con enlaces `openDocumento.do` |
| IDECyL WFS | GeoJSON | Sectores NUM vigentes con polígonos |

No hay visor urbanístico propio del ayuntamiento; la geometría procede del geoportal regional IDECyL.

## Licencias

- El tablón de la sede publica anuncios de licencia (p. ej. uso excepcional suelo rústico + licencia urbanística casilla agrícola).
- La web Drupal solo ofrece páginas informativas de solicitud de licencia (sin listado de concesiones históricas).
- El adapter incluye trámites informativos de la sede cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_sectores` (17 features), `urbanismo:plau_cyl_planes_parciales` (1), `urbanismo:plau_cyl_instrumentos_ambito` (1)
  - Filtro: `CQL_FILTER=n_mun='Ólvega'` (c_mun=42134)
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `c_instrum`
- **Estrategia:** descarga WFS con `srsName=EPSG:4326`; enriquecimiento por coincidencia de nombre de sector en títulos de tablón/PLAI/Drupal
- **Limitaciones:**
  - Sin visor municipal ArcGIS; solo capas regionales
  - Los anuncios de licencia del tablón no enlazan geometría puntual
  - PLAI y Drupal aportan metadatos/PDF sin coords

## Limitaciones generales

- Drupal 7 antiguo; sitemap desactualizado (muchas URLs de 2017)
- Sede espublico: certificado SSL válido pero se usa `insecure_ssl` por consistencia con otros municipios CYL
- Tablón sede con pocas filas (~10); histórico mayor en PLAI y edictos Drupal
- Sin API JSON pública; scrape HTML determinista

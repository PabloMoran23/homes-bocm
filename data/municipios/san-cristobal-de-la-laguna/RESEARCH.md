# San Cristóbal de La Laguna — investigación portal ayuntamiento

Municipio: **San Cristóbal de La Laguna** (`san-cristobal-de-la-laguna`) — Canarias, provincia Santa Cruz de Tenerife. Sin avisos BOCM asociados en cola. INE: 38023.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (OpenCMS / inSuit) | https://www.lalaguna.es |
| Urbanismo (sección servicios) | https://www.lalaguna.es/servicios/urbanismo-y-vivienda/ |
| Anuncios municipales | https://www.lalaguna.es/ayuntamiento/anuncios-municipales/ |
| Sede electrónica (Galileo iys) | https://sede.aytolalaguna.es |
| Tablón de edictos | https://sede.aytolalaguna.es/public/tea/TablonEdictos.aspx |
| RSS edictos | https://sede.aytolalaguna.es/publico/sindicacion/edictos/RSS |
| Procedimientos sede | https://sede.aytolalaguna.es/publico/procedimientos |
| Gerencia de Urbanismo (Drupal 10) | https://www.urbanismolalaguna.es |
| Anuncios gerencia (`type=anuncio`) | https://www.urbanismolalaguna.es/actualidad?type=anuncio |
| Planeamiento / PGO en trámite | https://www.urbanismolalaguna.es/planeamiento |
| Visor PGO 2004 (mapas estáticos) | http://maps.urbanismolalaguna.org/visor/pgoad2004.html |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-san-cristobal-de-la-laguna |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38023/ |

## Cómo se listan expedientes / planeamiento

- **Gerencia Drupal:** listados paginados en `/actualidad?type=anuncio` y `type=noticia` con rutas `/actualidad/expediente-*` (información pública, convenios urbanísticos, licencias).
- **Sede:** tablón HTML + **RSS** de edictos (`/publico/sindicacion/edictos/RSS`); mezcla notarial y urbanismo — filtro por keywords en el adapter.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN con **117 recursos** enlazando SIPU/GEOBDP/IDECanarias.
- **GEOBDP:** índice municipal con decenas de instrumentos aprobados; cada ficha incluye `App.Map.zoomToExtent` con geometría **EPSG:32628**.

## Licencias de obra

- **Anuncios Drupal** publican solicitudes de licencia de usos y obras (información pública, PDF adjunto en `field-anuncio-documentos`).
- **No hay dataset abierto** de licencias concedidas con coordenadas; trámites en sede (`/publico/procedimientos`) y formulario incidencias urbanas.
- El adapter incluye filas informativas de trámites + licencias detectadas en anuncios/RSS.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza instrumentos de planeamiento a GEOBDP
  - Visor `maps.urbanismolalaguna.org` — capas del PGO 2004 sin API de consulta por expediente individual
- **Estrategia:** emparejar títulos SITCAN ↔ documentos GEOBDP; reproyectar EPSG:32628 → WGS84; anuncios de licencia sin enlace GIS.
- **Limitaciones:** geometría solo para instrumentos de planeamiento en GEOBDP; licencias y edictos sede sin polígono; visor histórico no enlazable por código de expediente.

## Limitaciones generales

- Portal principal sin sitemap público; dependencia de semillas + Drupal.
- RSS sede muy heterogéneo (notaría, presupuestos, etc.).
- Sin re-parse BOCM regional (0 avisos en cola para este municipio).

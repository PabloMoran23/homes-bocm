# Puerto del Rosario — investigación portal ayuntamiento

Municipio: **Puerto del Rosario** (`puerto-del-rosario`) — Canarias, Las Palmas (Fuerteventura). Sin avisos en boletín regional asociados en cola. INE: **35017**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo (WordPress) | https://www.puertodelrosario.org |
| Urbanismo | https://www.puertodelrosario.org/ayuntamiento/areas-tematicas/urbanismo/ |
| Transparencia — ordenación del territorio | https://transparencia.puertodelrosario.org/es/ordenacion-del-territorio |
| Transparencia — plan insular / PGO | https://transparencia.puertodelrosario.org/es/informacion-del-plan-insular-o-general-de-ordenacion-y-de-los-planes-y-proyectos-de-desarrollo-del |
| Sede electrónica | https://puertodelrosario.sedelectronica.es |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-puerto-del-rosario |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35017/ |
| IDECanarias (índices PGO) | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/FV/PtRs/ |

## Cómo se listan expedientes / planeamiento

- **Portal WordPress:** sección Urbanismo con enlaces a normativa y trámites. En el entorno cloud del agente responde **captcha SiteGround** (HTTP 202 → `/.well-known/sgcaptcha/`), por lo que el scrape directo de `www.puertodelrosario.org` no es fiable en CI.
- **Portal de transparencia (Drupal 10):** ámbito «Ordenación del territorio» con documentación del PGO (ficheros en `/sites/puertodelrosario/files/…`, p. ej. `planeamiento.odt`) y enlaces a territorio canario / SITCAN. Accesible por **HTTP** sin captcha.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-puerto-del-rosario` con recursos FIP/ZIP, enlaces GEOBDP e IDECanarias para el PGO y una modificación puntual (2017).
- **GEOBDP Grafcan:** listado municipal con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N). Documentos conocidos: 840 (PGO), 1256 (modificación puntual).
- **Sede electrónica:** dominio `puertodelrosario.sedelectronica.es` (espublico); rutas típicas de tablón/RSS devuelven **404** — sin listado público scrapeable de edictos en las URLs probadas.

## Licencias de obra

- **Sin dataset** abierto de licencias concedidas con dirección o coordenadas.
- Trámites vía sede electrónica y área de Urbanismo del portal; no hay tablón de anuncios con filas estructuradas accesible desde CI.
- El adapter incluye **páginas informativas** (sede, urbanismo, transparencia, SITCAN).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP (`geobdp.grafcan.es/core/documentos/...`)
- **Estrategia:** indexar documentos GEOBDP del municipio (35017); emparejar por título con recursos SITCAN; reproyectar EPSG:32628 → WGS84 en el adapter.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (pocos documentos activos en el índice municipal); portal corporativo con captcha; sin geometría para licencias de obra.

## Limitaciones generales

- Captcha SiteGround en `www.puertodelrosario.org` desde CI.
- Sede sin tablón/RSS usable en URLs estándar.
- Sin listado abierto de licencias concedidas.

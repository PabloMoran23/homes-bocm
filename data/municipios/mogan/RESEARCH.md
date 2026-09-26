# Mogán — investigación portal ayuntamiento

Municipio: **Mogán** (`mogan`) — Canarias, Gran Canaria. Boletín: `boc_canarias` (1 aviso). INE: **35012**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo | https://www.mogan.es |
| Urbanismo | https://www.mogan.es/40-urbanismo |
| Planeamiento (PGO, normas subsidiarias, planes parciales) | https://www.mogan.es/40-urbanismo/50-planeamiento |
| OAT — sede electrónica (ventanilla) | https://oat.mogan.es:8448/ventanilla/web/inicioWebc.do?opcion=noreg |
| espublico (dominio genérico, sede indeterminada) | https://mogan.sedelectronica.es |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-mogan |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35012/ |

## Cómo se listan expedientes / planeamiento

- **Portal municipal:** CMS propio con sección Urbanismo → Planeamiento (tablas de anexos PDF: normas subsidiarias, PGO, planes parciales, estudios de detalle, convenios). Enlace explícito a instrumentos publicados en **SITCAN-GOBCAN**. El sitio responde **HTTP 403** a crawlers en el entorno del agente (WAF/CDN).
- **OAT (Oficina de Atención Telemática):** sede Java en `oat.mogan.es:8448` con categoría «Urbanismo, Fomento y Actividades» y «Tablón Edictos». Acceso público sin certificado para consulta de trámites; conexión **intermitente/timeout** desde CI.
- **espublico gestiona:** `mogan.sedelectronica.es` devuelve página «Sede Electrónica Indeterminada» (sin tablón usable en el dominio genérico).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-mogan` con **342 recursos** (~92 instrumentos únicos por nombre): FIP/SIPU/ZIP y enlaces a GEOBDP e IDECanarias.
- **GEOBDP Grafcan:** **88** documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Licencias y comunicaciones previas vía OAT (trámites «Urbanismo, Fomento y Actividades») y tablón de edictos; no hay listado scrapeable estable desde espublico.
- El adapter incluye **páginas informativas** (OAT, planeamiento web, SITCAN).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP (`geobdp.grafcan.es/core/documentos/...`)
- **Estrategia:** indexar documentos GEOBDP del municipio (35012); emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84 (`municipio/geometry.py` / helper UTM28N del adapter).
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP; portal municipal y OAT no accesibles de forma fiable en CI; sin geometría para licencias de obra ni tablón de edictos.

## Limitaciones generales

- WAF 403 en `www.mogan.es` desde el entorno cloud del agente.
- OAT con timeouts; espublico sin sede resuelta.
- Sin listado abierto de licencias concedidas.

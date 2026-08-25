# Adeje — investigación portal ayuntamiento

Municipio: **Adeje** (`adeje`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (2 avisos BOC).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.ayuntamientodeadeje.es (inaccesible desde CI: timeout/000) |
| Sede electrónica (espublico gestiona) | https://adeje.sedelectronica.es |
| Tablón de anuncios | https://adeje.sedelectronica.es/board |
| Trámites (dossier) | https://adeje.sedelectronica.es/dossier |
| Normativa urbanística (citizen-service) | https://adeje.sedelectronica.es/citizen-service/481ea75d-2411-4f93-8dc9-19f0deae5af9 |
| SITCAN — planeamiento urbanístico | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-adeje |
| GEOBDP Grafcan (municipio 38001) | https://geobdp.grafcan.es/core/municipios/38001/ |
| IDECanarias (índices planos) | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Adje/ |

## Cómo se listan expedientes / planeamiento

- **CMS sede:** espublico gestiona (Apache Wicket). Tablón en `/board` con filas HTML (`class_name`, `class_description`, `class_folderCode`, `preview-document/{uuid}`).
- **Planeamiento sistematizado:** dataset CKAN SITCAN `planeamiento-urbanistico-de-adeje` (61 recursos: PGO, modificaciones, estudios de detalle, planes parciales, etc.) con enlaces a GEOBDP, IDECanarias y ZIP FIP.
- **GEOBDP:** listado municipal con 17 instrumentos de planeamiento aprobados (PGO 2007, modificaciones, estudios de detalle, plan parcial SN3, etc.).
- **Web corporativa:** `ayuntamientodeadeje.es` no responde desde el entorno del agente; los anuncios de información pública se publican en BOC y en sede (`/info`, tablón).
- **No hay** consulta pública de expedientes urbanísticos individualizados sin login (`/expedientes` requiere identificación).

## Licencias de obra

- **Sin dataset** de licencias concedidas publicado en listado abierto.
- **Tablón sede:** puede incluir edictos de licencias cuando se publican; en la muestra actual predominan convocatorias de plenos y acuerdos administrativos.
- **Trámites informativos:** catálogo `/dossier` (carga lenta) y citizen-service «Normativa urbanística».
- El adapter devuelve páginas informativas de sede + filas del tablón filtradas por keywords urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **GEOBDP Grafcan** — `https://geobdp.grafcan.es/core/documentos/{id}.html` embebe `App.Map.zoomToExtent(FeatureCollection)` en EPSG:32628 (UTM 28N); reprojectar a WGS84.
  - **IDECanarias** — índices HTML de planos (sin geometría vectorial directa).
  - No hay visor municipal propio accesible (web corporativa caída).
- **Estrategia:** emparejar título SITCAN/GEOBDP → `documentos/{id}` → extraer polígono MultiPolygon y rellenar `geom_geojson`.
- **Limitaciones:** geometría solo para instrumentos de planeamiento en GEOBDP (~17 docs); licencias y anuncios del tablón sin coords; web corporativa inaccesible desde CI.

## Limitaciones generales

- Portal principal `ayuntamientodeadeje.es` timeout desde CI (no bloquea: SITCAN+GEOBDP+sede cubren planeamiento).
- Tablón sede sin paginación API; scrape HTML estático.
- `/dossier` muy lento (>25s); se usa como enlace informativo, no crawl completo.
- Licencias: solo trámites informativos + tablón (sin listado histórico).

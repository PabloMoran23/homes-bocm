# Santa María de Guía — investigación portal ayuntamiento

Municipio: **Santa María de Guía** (`santa-maria-de-guia`) — Canarias, provincia Santa María de Guía (Gran Canaria). Boletín: `boc_canarias` (2 avisos BOCM).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://santamariadeguia.es |
| Área desarrollo urbanismo | https://santamariadeguia.es/area-de-desarrollo-urbanismo/ |
| PGO 2017 (externo) | http://www.plangeneralguiagc.es/PGO2017/inicio.html |
| Plan director zonas comerciales | http://www.plangeneralguiagc.es/plandirectorzonascomerciales2018/inicio.html |
| Sede electrónica | https://santamariadeguia.sedelectronica.es |
| Tablón de anuncios | https://santamariadeguia.sedelectronica.es/board |
| Trámites urbanismo (dossier) | http://santamariadeguia.sedelectronica.es/dossier.10 |
| Transparencia urbanismo | https://santamariadeguia.sedelectronica.es/transparency/bbdc5edb-e4ef-4bd8-8799-a276fcb12f47/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-santa-maria-de-guia-de-gran-canaria |
| GEOBDP municipio (INE 38038) | https://geobdp.grafcan.es/core/municipios/38038/ |
| IDECanarias RPGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/SMGu/RPGO/indice.html |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress con LiteSpeed cache (`santamariadeguia.es`); PDFs en `/wp-content/uploads/`.
- **Área urbanismo:** ordenanzas de urbanización/edificación, ordenanzas provisionales (SUCU 1.7, ampliación residencia Tarazona), planos PGOU por sector, catálogo de viviendas.
- **Sede espublico gestiona:** tablón `/board` con tablas HTML por categoría (edictos, subastas, etc.); dossier `.10` con trámites de urbanismo.
- **SITCAN CKAN:** 3 instrumentos de planeamiento sistematizado (adaptación PGO 2005, revisión PGO 2017, PEPRI 2000) con enlaces a GEOBDP e IDECanarias.
- **No hay** visor municipal de expedientes individualizados con código enlazable; consulta de expedientes vía sede con identificación.

## Licencias de obra

- **Sin dataset** histórico de licencias concedidas en web abierta.
- **Formularios y trámites** en sede `/dossier.10` (licencias obra, segregación, etc.).
- **Ordenanzas PDF** en área urbanismo (urbanización, edificación).
- El tablón puede publicar edictos de licencias puntualmente; no hay listado estructurado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **GEOBDP Grafcan** (`geobdp.grafcan.es/core/documentos/{id}.html`): polígonos de instrumentos de planeamiento via `App.Map.zoomToExtent` (EPSG:32628 UTM28N → reproyectar WGS84).
  - **SITCAN CKAN:** recursos con URL directa a GEOBDP (docs 659, 1099, 1446).
  - **IDECanarias:** índices HTML del RPGO/PEPRI sin API GeoJSON directa.
- **Estrategia:** tras obtener metadatos SITCAN, consultar GEOBDP por título/documento y extraer `geom_geojson`. Expedientes del tablón/PDF sin enlace GIS → sin geometría.
- **Limitaciones:** geometría solo para instrumentos de planeamiento regional (PGO/PEPRI), no para licencias ni expedientes individuales del tablón. PDFs de ordenanzas sin georreferenciación vectorial.

## Limitaciones generales

- Sin sitemap WordPress accesible; crawl por páginas semilla fijas.
- Sede espublico gestiona (no Galileo GIYS); sin RSS de edictos (`/publico/sindicacion/edictos/RSS` → 404).
- PGO externo en `plangeneralguiagc.es` fuera del dominio municipal.
- Licencias: solo trámites informativos; el orquestador aplicará centroide + jitter cuando no haya polígono.

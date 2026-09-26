# Garachico — investigación portal ayuntamiento

Municipio: **Garachico** (`garachico`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso BOCM). INE: 38015.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress) | https://www.garachico.es |
| Sede electrónica (espublico gestiona) | https://garachico.sedelectronica.es |
| Tablón de anuncios | https://garachico.sedelectronica.es/board |
| Transparencia económica (eadmin) | https://eadmin.garachico.es/transparencia |
| Plan general de ordenación (WP) | https://www.garachico.es/?page_id=1108 |
| Normas subsidiarias 1993 (WP) | https://www.garachico.es/?page_id=2016 |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-garachico |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38015/ |
| Licencia obra (Gob. Canarias) | https://sede.gobiernodecanarias.org/sede/tramites/1186 |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress 7 + tema `local-government`; REST API deshabilitada (401).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-garachico` con **13 recursos** (4 instrumentos únicos: PGO 2012, normas subsidiarias 1994 y 3 modificaciones puntuales).
- **GEOBDP:** 4 documentos con visor OpenLayers y botón «Localizar» (`findRecintoByDocumento`); geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Transparencia WP:** páginas `page_id=1108` (PGO) y `page_id=2016` (normas subsidiarias) con PDFs en `wp-content/uploads/`.
- **Tablón sede:** HTML tabla espublico en `/board` (5 anuncios recientes; mayoría presupuestos/cobranzas; filtro por keywords urbanismo).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica espublico (`/dossier`) y sede Gobierno de Canarias (tramite 1186).
- El adapter incluye páginas informativas del tablón, catálogo de trámites y enlace regional.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP
  - IDECanarias WMS regional sin query por expediente municipal
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38015); emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (4 polígonos); licencias y tablón sin geometría enlazable; WP REST deshabilitada.

## Limitaciones generales

- Tablón sede con pocos anuncios y sin licencias urbanísticas recientes.
- Sin listado histórico de licencias concedidas en abierto.
- `eadmin.garachico.es` portal transparencia ASP.NET (lento; sin datos urbanísticos estructurados).
- PDFs normativa en WP sin georreferencia directa.

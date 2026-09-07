# Arucas — investigación portal ayuntamiento

Municipio: **Arucas** (`arucas`) — Canarias, provincia Las Palmas (Gran Canaria). Boletín: `boc_canarias` (1 aviso). INE: 35006.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal municipal (PHP propio) | https://www.arucas.org |
| Urbanismo (sección servicios) | https://www.arucas.org/modules.php?mod=portal&file=ver_gen&tipo=99&id=TkRrM05RPT0= |
| PMUS — aprobación inicial (noticia) | https://www.arucas.org/modules.php?mod=portal&file=ver_gen&id=T1RNMU5RPT0= |
| Servicios municipales | https://www.arucas.org/modules.php?mod=portal&file=ver_servicios&id=TlRBMk13PT0= |
| Sede electrónica (espublico gestiona) | https://arucas.sedelectronica.es |
| Tablón de anuncios | https://arucas.sedelectronica.es/board |
| Portal transparencia sede | https://arucas.sedelectronica.es/transparency |
| Ordenanzas (transparencia sede) | https://arucas.sedelectronica.es/transparency/ac8b9712-ed87-457b-a683-263683c6b144/ |
| Trámites sede | https://arucas.sedelectronica.es/dossier |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-arucas |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35006/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Aruc/ |

## Cómo se listan expedientes / planeamiento

- **Portal corporativo:** CMS PHP (`modules.php?mod=portal`) con noticias/eventos; la sección «URBANISMO» enlaza sobre todo a la sede (tablón, ordenanzas, trámites). Destaca el PMUS (Plan de Movilidad Urbana Sostenible) como noticia con imagen/PDF en `documentos/`.
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label`: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación). ~10 anuncios recientes; mayoría empleo/subvenciones; exposiciones públicas esporádicas.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-arucas` con 18 recursos (5 instrumentos únicos × SIPU/IDECanarias/GEOBDP/FIP): PGO (anulado TS 2021), PERI centro histórico + modificación, normas subsidiarias, sentencia anulación.
- **GEOBDP Grafcan:** 4 documentos activos en índice municipal + doc. 725 (PGO anulado, features vacías); geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **No hay** visor de expedientes urbanísticos individuales ni API JSON del ayuntamiento.

## Cómo se publican licencias

- **Sin dataset** público de licencias de obra concedidas con dirección/coordenadas.
- Trámites vía sede electrónica (`/dossier`); tablón publica anuncios genéricos (empleo, subvenciones, convocatorias).
- Ordenanzas municipales en portal transparencia sede (incluye urbanismo).
- El adapter devuelve páginas informativas de trámites; licencias reales publicadas = 0 salvo anuncios puntuales en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (docs 726, 727, 1323, 1352 con geometría; 725 PGO anulado sin features)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es/ServicioWMS/Planeamiento`) sin query por expediente
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 35006); emparejar por título con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~4/5 con polígono); PMUS y noticias web sin geometría enlazable; tablón sin coords; sin listado abierto de licencias.

## Limitaciones generales

- Sección urbanismo web municipal escasa (enlaces a sede); contenido principal en SITCAN/GEOBDP.
- Tablón sede sin histórico completo ni filtro por categoría urbanismo.
- PGO de Arucas anulado por TS (1298/2020); GEOBDP doc 725 sin polígonos.
- Sin re-parse BOCM; 1 entrada en `boc_canarias` ya en `projects.json`.

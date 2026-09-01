# La Guancha — investigación portal ayuntamiento

Municipio: **La Guancha** (`la-guancha`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (2 avisos BOCM). INE: 38026.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress Bones) | https://www.laguancha.es |
| Departamento urbanismo | https://www.laguancha.es/ayuntamiento-2/departamentos/d-urbanismo/ |
| Categoría urbanismo (WP) | https://www.laguancha.es/category/urbanismo/ |
| Sede electrónica (espublico gestiona) | https://laguancha.sedelectronica.es |
| Tablón de anuncios | https://laguancha.sedelectronica.es/board/975040b6-f59b-11de-b600-00237da12c6a/ |
| Bandos y avisos | https://laguancha.sedelectronica.es/board/974e6d5e-f59b-11de-b600-00237da12c6a/ |
| Transparencia — ordenanzas | https://laguancha.sedelectronica.es/transparency/aec0d65b-fe1c-41d4-b280-21d7bc835c3a/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-la-guancha |
| IDECanarias PGO índice | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Guan/PGO/indice.html |
| GEOBDP documentos | https://geobdp.grafcan.es/core/documentos/985/ (PGO), 1134 (ED vial), 1348 (OME) |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + tema Bones + Yoast SEO (`laguancha.es`). Pocas noticias en categoría urbanismo; el departamento publica enlaces a sede y PDFs puntuales.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-la-guancha` con **3 instrumentos** (PGO adaptación DL 1/2000, estudio de detalle vial XXV Noviembre–El Roque, ordenanzas municipales edificación/urbanización).
- **GEOBDP:** cada instrumento SITCAN enlaza a `geobdp.grafcan.es/core/documentos/{id}.html` con geometría embebida en `App.Map.zoomToExtent({...})` (CRS **EPSG:32628** UTM 28N).
- **Sede espublico:** tablón y bandos en HTML con tabla Wicket (`class_name`, `class_folderCode`, `class_folderName`, `preview-document/{uuid}`). Incluye anuncios BOP de planeamiento y bandos de legalidad urbanística.
- **IDECanarias:** índices HTML con PDFs del PGO y estudios de detalle (sin API de listado).
- **No hay** listado público de expedientes urbanísticos individualizados (consulta en `/expedientes` requiere identificación).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Tablón sede puede publicar edictos de licencias/actividad cuando proceda; actualmente pocos avisos urbanísticos.
- Trámites vía catálogo `/dossier` (espublico; carga lenta). El adapter incluye páginas informativas del tablón y catálogo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (docs 985, 1134, 1348)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional `https://idecan2.grafcan.es/ServicioWMS/Planeamiento` (sin query por código de expediente)
  - Portal GeoBDP histórico: https://geobdp.grafcan.es/
- **Estrategia:** emparejar recursos SITCAN por título con documento GEOBDP; descargar `zoomToExtent` y reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo 3 instrumentos de planeamiento en GEOBDP; tablón/bandos y licencias sin geometría enlazable; WP con escaso contenido urbanístico estructurado.

## Limitaciones generales

- Catálogo de trámites `/dossier` muy lento desde CI (timeout posible; no bloquea ingesta principal).
- Sin visor urbanístico municipal propio; planeamiento regional vía Grafcan/IDECanarias.
- Categoría WP `urbanismo` casi vacía; fuente principal = SITCAN + tablón sede.
- Sin licencias concedidas en listado abierto; solo trámites informativos y edictos puntuales.

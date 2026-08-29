# La Matanza de Acentejo — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa (WordPress) | https://www.matanceros.es |
| Tablón de anuncios (WP) | https://www.matanceros.es/tablon-de-anuncios/ |
| Transparencia | https://www.matanceros.es/transparencia/ |
| Oficina técnica | https://www.matanceros.es/areas-municipales/oficina-tecnica/ |
| Vivienda | https://www.matanceros.es/vivienda/ |
| Bandos municipales | https://www.matanceros.es/bandos-municipales/ |
| Sede electrónica (espublico gestiona) | https://matanceros.sedelectronica.es |
| Tablón sede (Wicket) | https://matanceros.sedelectronica.es/board/ |
| SITCAN CKAN | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-la-matanza-de-acentejo |
| GEOBDP municipio (INE 38025) | https://geobdp.grafcan.es/core/municipios/38025/ |

## Cómo se listan expedientes

- **SITCAN CKAN**: dataset `planeamiento-urbanistico-de-la-matanza-de-acentejo` con 6 instrumentos de planeamiento (PGOU, ordenanzas, revisiones parciales). Cada recurso enlaza a PDF CKAN, índice IDECanarias y visor GEOBDP (`geobdp.grafcan.es/core/documentos/{id}`).
- **Sede electrónica**: tablón `/board/` con tabla Wicket (`class_name`, `class_folderCode`, `preview-document/{uuid}`). Categoría «Urbanismo» incluye certificados/informes urbanísticos (p. ej. estudio de detalle expediente 1855/2025).
- **WordPress**: noticias y páginas estáticas; sitemap Yoast (`post-sitemap.xml`). Pocas entradas específicas de urbanismo; el tablón WP redirige a la sede.

## Licencias de obra

No hay dataset histórico de licencias concedidas. La sede publica trámites y el tablón incluye anuncios puntuales (ordenanzas, informes). El adapter devuelve páginas informativas de la sede y entradas del tablón que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP Grafcan: `App.Map.zoomToExtent` en páginas `/core/documentos/{id}.html` (coordenadas EPSG:32628 UTM28N, reproyectadas a WGS84).
  - IDECanarias: índices HTML en `idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Mtnz/...` (sin API GeoJSON directa).
  - SITCAN enlaza documentos GEOBDP (IDs 962, 1397, 1407, 1408, 1490, 1494).
- **Estrategia:** emparejar título SITCAN/CKAN con documento GEOBDP por URL o índice de títulos del municipio; extraer polígono del visor Grafcan.
- **Limitaciones:** solo instrumentos de planeamiento general/ordenanzas tienen polígono municipal; expedientes del tablón sede (estudios de detalle, licencias) son PDF sin georreferencia enlazable. INE 38025.

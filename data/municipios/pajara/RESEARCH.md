# Pájara — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.pajara.es |
| Urbanismo | https://www.pajara.es/areas/urbanismo/ |
| Plan general (PGOU) | https://www.pajara.es/plan-general-de-ordenacion/ |
| Ordenación estructural / pormenorizada | https://www.pajara.es/plan-general-de-ordenacion/ordenacion-estructural-oe/ , https://www.pajara.es/plan-general-de-ordenacion/ordenacion-pormenorizada-op/ |
| Modelos oficina técnica (licencias) | https://www.pajara.es/modelos-300-oficina-tecnica/ |
| Urbanismo en Red (histórico) | https://www.pajara.es/urbanismo-en-red/ |
| Sede electrónica | https://sede.pajara.es |
| Tablón de anuncios | https://sede.pajara.es/eAdmin/Tablon.do?action=verAnuncios |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-pajara |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35015/ |

## Cómo se listan expedientes / proyectos

- **SITCAN (CKAN):** dataset `planeamiento-urbanistico-de-pajara` con ~81 recursos (PDF/ZIP por instrumento: PP, modificaciones, NS, etc.). API `package_show`.
- **GEOBDP:** índice HTML del municipio con enlaces `/core/documentos/{id}.html`; geometría embebida en `App.Map.zoomToExtent({FeatureCollection})` (UTM 28N, reproyectado a WGS84 en el adapter).
- **Web WP:** páginas de PGOU y urbanismo con documentos vía plugin WP File Download; PDFs enlazados en HTML.
- **Tablón sede:** listado `Tablon.do?action=verAnuncios` con anuncios por ID; detalle en `verAnuncio&id=…` (ISO-8859-1). Pocos anuncios de obra/licencia urbana (mayoría empleo/tributos).

## Licencias de obra

- No hay dataset público de concesiones georreferenciadas.
- Formularios informativos en `modelos-300-oficina-tecnica/` y trámites vía sede.
- Tablón puede publicar edictos puntuales; el adapter incluye páginas de trámite + anuncios que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** GEOBDP Grafcan `https://geobdp.grafcan.es/core/municipios/35015/` — documentos de planeamiento con polígonos en página del visor OpenLayers; recursos SITCAN enlazan al mismo visor cuando incluyen URL `geobdp.grafcan.es`.
- **Estrategia:** tras ingestar título de proyecto (SITCAN o web), emparejar título con índice GEOBDP y extraer `zoomToExtent` → GeoJSON WGS84.
- **Limitaciones:** licencias del tablón sin enlace GIS; instrumentos solo PDF sin entrada GEOBDP no tendrán polígono. Coordenadas UTM en visor requieren reproyección manual (patrón Canarias compartido con Arucas/Haría).

## Limitaciones generales

- Sede `pajara.sedelectronica.es` redirige a selector; la sede operativa es `sede.pajara.es`.
- Tablón con encoding Latin-1.
- `request_delay_s` recomendado por volumen SITCAN + detalle tablón.

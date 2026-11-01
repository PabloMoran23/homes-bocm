# Puerto de la Cruz — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.puertodelacruz.es |
| Ciudad Sostenible (urbanismo/trámites) | https://ciudadsostenible.puertodelacruz.es |
| Planeamiento / normativa | https://ciudadsostenible.puertodelacruz.es/planeamiento/ |
| Catálogo trámites | https://ciudadsostenible.puertodelacruz.es/tramites/ |
| Sede electrónica | https://puertodelacruz.sedelectronica.es |
| Tablón de anuncios | https://puertodelacruz.sedelectronica.es/board |
| SITCAN CKAN | `planeamiento-urbanistico-de-puerto-de-la-cruz` |
| GEOBDP municipio (INE 38039) | https://geobdp.grafcan.es/core/municipios/38039/ |

## Listado de expedientes / planeamiento

- **Ciudad Sostenible:** WordPress (Divi). Páginas de planeamiento con PDFs de ordenanzas (edificación, urbanización) y enlaces a trámites (licencia urbanística 210.02, cédula 210.01, ocupación vía pública).
- **Sede espublico gestiona:** tablón HTML con filas `data-label` (Documento, Descripción, Procedimiento, Categoría, Expediente, Fecha de Publicación). Enlaces a documentos vía Wicket/AJAX (se usa la URL del tablón como referencia).
- **SITCAN:** dataset CKAN con recursos por instrumento de planeamiento (nombres de planes/figuras); algunos enlazan a GEOBDP.
- **GEOBDP:** índice municipal con documentos cartográficos; cada ficha incluye `App.Map.zoomToExtent(FeatureCollection)` en EPSG:32628.

## Licencias de obra

No hay listado público de licencias concedidas con coordenadas. Fuentes:

- Tablón de anuncios (edictos/notificaciones urbanísticas cuando se publican).
- Trámites informativos en Ciudad Sostenible (210.02 licencia urbanística).
- Trámite regional Gobierno de Canarias (licencia de obra): https://sede.gobiernodecanarias.org/sede/tramites/1186

El adapter incluye filas informativas de tablón + trámites y extrae del tablón entradas que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** GEOBDP Grafcan (`geobdp.grafcan.es/core/documentos/{id}.html`), capas de planeamiento vinculadas desde SITCAN; CRS origen EPSG:32628 (UTM 28N), reproyectado a WGS84 en el adapter.
- **Estrategia:** indexar títulos del índice GEOBDP del municipio 38039; al crear cada fila de proyecto (SITCAN/GEOBDP/WP), hacer match por título o URL `geobdp.grafcan.es` y parsear `zoomToExtent` → `geom_geojson`.
- **Limitaciones:** expedientes del tablón y licencias puntuales no llevan enlace GIS; solo instrumentos de planeamiento catalogados en GEOBDP/SITCAN tienen polígono. No hay visor ArcGIS municipal propio; el visor útil es el de Grafcan vía GEOBDP.

## Limitaciones generales

- Tablón con pocos anuncios visibles en HTML estático (paginación Wicket).
- Licencias sin dataset abierto municipal.
- Web corporativa separada de Ciudad Sostenible (menos contenido urbanístico que el portal temático).

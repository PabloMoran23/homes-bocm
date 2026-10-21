# Toledo — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|--------|-----|
| Web corporativa | https://www.toledo.es |
| Urbanismo (listado) | https://www.toledo.es/servicios-municipales/urbanismo/ |
| RSS categoría Urbanismo | https://www.toledo.es/category/urbanismo/feed/ |
| PGMOU 1986 (repositorio PDF) | https://www.toledo.es/servicios-municipales/urbanismo/plan-general-de-ordenacion-urbana-1986/ |
| Sede electrónica (inicio) | https://sede.toledo.es/eAdmin/Sede.do |
| Tablón de anuncios | https://sede.toledo.es/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo procedimientos (ALHAJA) | https://a2.toledo.es/sede/catalogo |

## Proyectos / planeamiento

- **WordPress:** las actuaciones de información pública y estudios de detalle se publican como entradas en la categoría *Urbanismo*, con enlaces a PDFs en `wp-content/uploads/`. El feed RSS expone las ~10 entradas más recientes; el listado `/servicios-municipales/urbanismo/page/N/` enlaza a posts históricos.
- **Tablón sede:** HTML tabular (`verAnuncio&id=…`, periodo de publicación, PDF vía `abrirOriginal('token')` → `ValidarDocumento.do`). Búsqueda POST con `referenciaBusqueda` (mismo patrón que otros ayuntamientos eAdmin/add4u).
- **PGMOU:** gran volumen de PDF estático en la página del plan; el adapter prioriza RSS + posts recientes + tablón para no descargar cientos de planos históricos.

## Licencias

- No hay listado público de concesiones de licencia de obra en tablón de forma sistemática (sí noticias de gestión interna).
- Trámites informativos en **ALHAJA** (`a2.toledo.es/sede/procedimiento/…`): obra mayor/menor, licencias urbanísticas, apertura, cambio de uso, vado, etc.
- Solicitud general legacy: `sede.toledo.es/eAdmin/Registrar.do?action=infoTramite&tipoReg=2`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes regionales (no enlazadas a expediente municipal):**
  - Visor SIU Castilla-La Mancha: https://castillalamancha.maps.arcgis.com/apps/webappviewer/index.html?id=c2179eb… (capas de planeamiento autonómico, sin código de expediente del ayuntamiento).
  - Datos abiertos CLM — SIU / planeamiento municipal (shapefile agregado, sin API por anuncio).
- **Estrategia adapter:** sin `geom_geojson`; el orquestador usa centroide municipal (`manifest.portal.config.centroid`) + jitter en geocode.
- **Limitaciones:** PDFs y noticias sin georreferencia; no hay visor municipal ArcGIS/WFS con campo expediente; el PGMOU se ofrece solo como planos PDF.

## Limitaciones técnicas

- Tablón responde en **ISO-8859-1** (no UTF-8).
- El tablón vigente mezcla anuncios urbanísticos con recursos humanos y edictos; se filtra por regex y búsquedas temáticas.
- `a2.toledo.es` es SPA ALHAJA; solo se scrapean URLs estables de procedimiento.

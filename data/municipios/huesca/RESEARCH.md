# Investigación portal — Huesca

**Municipio:** Huesca (`huesca`)  
**Provincia / CCAA:** Huesca / Aragón  
**INE municipio:** 22125

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web ayuntamiento | https://www.huesca.es | Liferay 7.x (`com.liferay.*`, `/documents/`, `/w/`) |
| Área Urbanismo | https://www.huesca.es/areas/urbanismo | Menú planeamiento, ARRU, GeoInfo |
| Planeamiento | https://www.huesca.es/areas/urbanismo/planeamiento-urbanistico | PGOU, modificaciones aisladas (PDFs en `/documents/`) |
| Modificaciones PGOU | https://www.huesca.es/areas/urbanismo/planeamiento-urbanistico/modificaciones-aisladas-al-texto-refundido-del-pgou | ~20 PDFs MODIFICACIÓN n del PGOU |
| GeoInfo / visores | https://www.huesca.es/areas/urbanismo/geoinfohuesca | Enlaces a `gis.huesca.es` (TM, PGOU1980, barrios, etc.) |
| Sede electrónica | https://sedeelectronica.huesca.es/eAdmin/Sede.do | eAdmin (Maggioli) |
| Tablón anuncios | https://sedeelectronica.huesca.es/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1 | Tabla HTML con título + periodo de exposición |
| Catálogo trámites urbanismo | https://www.huesca.es/ayuntamiento/tramites-y-gestiones/catalogo-de-tramites/urbanismo | Licencias urbanísticas, ambientales, instancias habilitantes |

**Nota:** `huesca.sedelectronica.es` es un selector genérico; la sede operativa es `sedeelectronica.huesca.es`.

## Listado de expedientes / planeamiento

- **No hay** visor de expedientes urbanísticos abiertos tipo RPGUR ni API JSON pública.
- **Planeamiento:** documentos estáticos en Liferay (`/documents/33451/...` y `/documents/d/urbanismo/...`) en páginas de modificaciones PGOU y disposiciones sectoriales.
- **Noticias urbanísticas:** artículos `/w/...` enlazados desde el inicio del área de Urbanismo (licitaciones, convenios de reurbanización).
- **Tablón sede:** anuncios de información pública, licencias, aprobaciones; HTML scrapeable (`verAnuncio&id=...`, periodo `DD/MM/YYYY - DD/MM/YYYY`). En entornos con timeout a la sede, snapshot Wayback (2025-04-22) conserva el listado.

## Licencias de obra

- No hay dataset tabular de licencias concedidas con coordenadas.
- **Tablón:** edictos y anuncios que mencionan licencias / información pública (filtrados por regex en el adapter).
- **Trámites:** páginas Liferay `/-/licencias-urbanisticas`, `/-/licencia-ambiental-clasificada`, `/-/instancias-titulos-habilitantes-en-materia-urbanistica-y-otros`, etc. (informativas, sin listado de concesiones).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** `https://gis.huesca.es/TM`, `POLIGONOSPGOU1980`, `vertices`, visores temáticos (barrios, ZBE, etc.). Aplicaciones web ArcGIS / mapas municipales sin campo de enlace a expediente o código de licencia.
- **Estrategia:** no aplicable; el orquestador usará centroide municipal + jitter (`manifest.portal.config.centroid`).
- **Limitaciones:** visores no consultables por expediente desde el adapter; sede y GIS con timeout frecuente desde redes cloud (tablón vía Wayback como respaldo de metadatos).

## Limitaciones

- Sede `sedeelectronica.huesca.es` y `gis.huesca.es` pueden no responder desde CI/cloud (SSL/timeout); Liferay principal suele ser accesible.
- Tablón Wayback puede estar desactualizado respecto al tablón en vivo.
- Sin boletín regional asociado en cola (`bocm_count: 0`).

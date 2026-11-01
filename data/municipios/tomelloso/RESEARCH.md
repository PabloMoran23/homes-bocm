# Tomelloso — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Formato |
|--------|-----|---------|
| Web corporativa | https://www.tomelloso.es | Webflow CMS |
| Información urbanística | https://www.tomelloso.es/urbanismo-y-obras/informacion-urbanistica | Listas `w-dyn-item`, enlaces PDF (CDN Webflow) y Nextcloud Diputación |
| Gobierno abierto (normativa / ED) | https://www.tomelloso.es/ayuntamiento/gobierno-abierto/informacion-de-relevancia-juridica | Misma plantilla Webflow |
| Sede electrónica | https://www.tomelloso.es/sede | Catálogo de trámites |
| Trámites urbanismo | https://www.tomelloso.es/sede/catalogo/tramites-de-urbanismo-y-obras | Enlaces a fichas de trámite |
| Tablón edictos | https://etablon.dipucr.es:4443/eTablon/tablon.jsf?entidad=037 | JSF RichFaces (Diputación Ciudad Real) |

## Proyectos / expedientes

- La sección **Información urbanística** publica anuncios de información pública, PAU, convenios, estudios de detalle y documentación del PGOU (PDF/JPG).
- Cada tarjeta es un `div.w-dyn-item` con `a.link-tramite-verde` (visible) y título en `h6.paragraph`.
- Algunos documentos apuntan a `cdn.prod.website-files.com`; otros a carpetas Nextcloud de la Diputación (`nextcloud.dipucr.es`).
- **Gobierno abierto → Relevancia jurídica** incluye aprobaciones de estudios de detalle y consultas de ordenanzas (mismo patrón Webflow).

## Licencias de obra

- No hay tablón municipal con concesiones georreferenciadas.
- El catálogo de la sede describe trámites: licencia mayor/menor, comunicación previa, parcelación, licencia de actividades+obra.
- Estrategia del adapter: filas informativas por ficha de trámite (patrón Pozuelo), `fecha_concesion` nula.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** visor ArcGIS Online del ayuntamiento (`https://tos.maps.arcgis.com`, app `ef247e197ce4471a9b641b759b760ae1`) con capas de planeamiento/PGOU.
- **Estrategia:** no hay campo de expediente ni código en el listado Webflow que permita consultar polígonos por proyecto; el visor sirve para consulta cartográfica general.
- **Limitaciones:** documentación en PDF/planos sin georreferencia enlazada; eTablon solo entrega PDF del anuncio.

## Limitaciones técnicas

- eTablon usa certificado en puerto 4443 → `insecure_ssl: true` en el manifest.
- Tablón eTablon: descarga directa `…/eTablon/documentos/037/<nombreArchivo>.pdf` (extraído del HTML).
- Paginación del tablón: el adapter consume la primera página visible (suficiente para mezclar con Webflow).

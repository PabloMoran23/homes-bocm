# San Sebastián (La Gomera) — investigación portal ayuntamiento

Municipio: **San Sebastián** (`san-sebastian`) — nombre oficial **San Sebastián de La Gomera**  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias · INE: **38036**  
BOC: `boc_canarias` (1 entrada en cola; alias de slug `san-sebastian-de-la-gomera` con 2 en BOCM)

> Implementación compartida con `san-sebastian-de-la-gomera` (`municipio/adapters/san_sebastian_de_la_gomera.py`). Ver también `data/municipios/san-sebastian-de-la-gomera/RESEARCH.md`.

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://sansebastiangomera.org/ | WordPress; `www.sansebastiangomera.es` detrás de Cloudflare (403 en scrape) |
| Sede electrónica | https://eadmin.sansebastiangomera.org/ | Galileo GIYS |
| Tablón edictos | https://eadmin.sansebastiangomera.org/publico/tablon | HTML ASP.NET |
| RSS edictos | https://eadmin.sansebastiangomera.org/publico/sindicacion/edictos/RSS | Sindicación XML |
| Procedimientos URBANISMO | https://eadmin.sansebastiangomera.org/publico/procedimientos | Trámites informativos |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-san-sebastian-de-la-gomera | 42 recursos CKAN |
| GeoBDP municipio | https://geobdp.grafcan.es/core/municipios/38036/ | Visor polígonos por documento |

## Expedientes / proyectos

- **SITCAN:** instrumentos de planeamiento (PGO, modificaciones, estudios de detalle, SAPU) con enlaces IDE Canarias y GeoBDP.
- **Tablón + RSS sede:** edictos urbanísticos (aprobaciones, ordenanzas, exposiciones).
- **WordPress:** noticias de obras/servicios (sitemap).

## Licencias de obra

- Sin listado público de licencias concedidas con coordenadas.
- Trámites en sede (licencia de obra, comunicación previa) + edictos puntuales filtrados por regex.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** GeoBDP `geobdp.grafcan.es/core/documentos/{id}.html` — `App.Map.zoomToExtent` UTM28N → WGS84; catálogo municipal 38036.
- **Estrategia:** emparejar recurso SITCAN ↔ documento GeoBDP por título normalizado.
- **Limitaciones:** solo instrumentos de planeamiento en SITCAN (~15 polígonos); tablón/edictos y licencias sin GIS enlazable.

## Limitaciones generales

- Dominio `.es` con Cloudflare bloquea urllib; adapter usa `sansebastiangomera.org`.
- Sin API JSON en tablón (HTML + RSS).
- Expedientes en sede (`/publico/territorio/cexp`) sin geometría pública.
- IGN OGC API no devuelve límite municipal para este nombre; `manifest.yaml` usa contorno OSM simplificado (Nominatim) en `geometry.validation.municipal_boundary`.

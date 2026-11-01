# Ourense — investigación portal ayuntamiento

Municipio: **Ourense** (`ourense`) — Galicia, provincia Ourense. INE: **32054**.  
Cola BOCM: 1 entrada (`bocm`; la cola marca `comunidad-madrid` por ruido en el CSV regional — el municipio es gallego).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial | https://ourense.gal/ | CMS propio (Bootstrap), gl/es |
| Urbanismo | https://ourense.gal/gl/servizos/urbanismo-licencias-y-vivienda | Hub: guías licencias, ITE, taboleiro PDF, enlaces ORDE sede, noticias PXOM |
| Taboleiro (PDF) | https://ourense.gal/media/Areas/Urbanismo/Taboleiro/ | Anuncios y convenios (pocos PDF estáticos) |
| Sede electrónica | https://sede.ourense.gob.es/ | Publicaciones normativas ORDE, formularios; **TLS handshake timeout** desde cloud agent |
| Normativa municipal | https://sede.ourense.gob.es/public/dynamic/publications/municipalregulations/ | Catálogo ORDE |
| SIOTUGA | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Inventario planeamento Xunta (PXOM 1986 + nuevo PXOM en tramitación) |
| Noticias PXOM | `/gl/actualidad/...-plan-de-urbanismo-pxom` | Actualidad sobre aprobación PXOM |

## Expedientes / proyectos

- **Listado:** scrape del hub de urbanismo (`<a href>` + PDFs taboleiro/uploads), noticias urbanismo enlazadas, semillas ORDE (títulos desde la web) y SIOTUGA.
- **Formato:** HTML estático en ourense.gal; publicaciones planeamiento en sede ORDE (`/public/publications/list/municipalregulations/ORDE/details/{id}`).
- **ITE:** listados anuales de edificios sujetos a inspección (PDF); se excluyen del scrape de proyectos (no son expedientes de planeamiento).
- **Tablón sede:** `/board` no accesible en este entorno; el adapter intenta con timeout corto.

## Licencias

- No hay registro público de licencias concedidas con coordenadas.
- Guías informativas PDF (urbanísticas y actividad), fichas técnicas y ordenanza ITE en sede.
- Estrategia: filas informativas de trámites/guías (`min_rows: 0` aceptable en licencias).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Planos PXOM en sede (PDF/OR DE, sin API ArcGIS por expediente).
  - SIOTUGA / mapas Xunta: planeamiento municipal agregado, sin enlace query por código de expediente del ayuntamiento.
  - Web: sin visor urbanístico propio con WFS/GeoJSON.
- **Estrategia:** sin `geom_geojson`; orquestador usa centroide municipio + jitter (`centroid` en manifest).
- **Limitaciones:** sede inaccesible desde red del agente; taboleiro reducido a PDFs sueltos; PXOM nuevo en tramitación autonómica.

## Limitaciones técnicas

- `sede.ourense.gob.es`: timeout SSL/handshake fuera de Galicia/España; `insecure_ssl` no resuelve el bloqueo de red.
- Contenido bilingüe gl/es; semillas en gallego.
- ITE y subvenciones mezcladas en el hub — filtro por regex en adapter.

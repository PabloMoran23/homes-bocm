# Ceuta — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Portal web | https://www.ceuta.es/ceuta |
| PGOU 2023 (índice) | https://www.ceuta.es/ceuta/trpgouce |
| PGOU Tomo 3 (instrumentos) | https://www.ceuta.es/ceuta/la-institucion/normativa/152-paginas/paginas/pgou/paginas/4863-tomo-3-2023 |
| PGOU introducción | https://www.ceuta.es/ceuta/por-servicios/sede-electronica/152-paginas/paginas/pgou/paginas |
| Sede electrónica | https://sede.ceuta.es |
| Trámites urbanismo (tema) | `controlador?cmd=tramites&modulo=tramites&tema=urb` — tabla vacía sin JS |
| Trámites licencias (tema) | `controlador?cmd=tramites&modulo=tramites&tema=lic` |
| Tablón de anuncios | https://www.ceuta.es/ceuta/por-servicios/tablon — iframe embebido (no scrapeable) |
| BOCCE (jDownloads) | `component/jdownloads/viewcategory/*` (p. ej. `1978-julio`, `1971-marzo`) |
| Boletín BOCCE ejemplo | `component/jdownloads/finish/.../bocce-6599-...` |

## Listado de expedientes / planeamiento

- **PGOU 2023:** páginas Joomla con tablas de instrumentos (APE, APR, PEPCH, SUP) y enlaces jDownloads a PDFs/memorias/planos. Aprobación definitiva parcial 28/12/2023 (Orden TMA 840/2023).
- **Tomo 5 y 6:** mapas interactivos (clic en imagen) para retícula de planos; no API REST pública en el HTML estático.
- **BOCCE:** sumarios HTML/PDF en jDownloads; entradas numeradas con decretos de Urbanismo, información pública de licencias de apertura/actividad, etc.
- **Sede:** trámites por código (`tramite=OMAY`, `SPE`, `SGBB`, …); páginas informativas, no listado de expedientes abiertos.

## Licencias de obra

No hay registro público de licencias concedidas con dirección y coordenadas. Fuentes:

1. Sede — licencia obra mayor (`OMAY`), menor viviendas (`LOM`), primera ocupación (`SLDPO`), etc.
2. BOCCE — anuncios de información pública de licencias de apertura/actividad (texto en sumario).
3. Tablón físico/digital embebido sin API.

El adapter devuelve **trámites sede** + **anuncios BOCCE** filtrados, no concesiones georreferenciadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Mapas interactivos PGOU (Tomo 5 calificación, Tomo 6 gestión) en portal; callejero municipal. Sin WFS/ArcGIS/GeoJSON público enlazado a expediente o licencia.
- **Estrategia:** No hay query determinista por código de expediente. Orquestador usa `centroid` en manifest + jitter.
- **Limitaciones:** Contenido tras iframe en tablón; SSL/TLS del host `www.ceuta.es` puede ser lento o no responder desde algunos datacenters; instrumentos PGOU mayormente PDF.

## Limitaciones generales

- Listado `tema=urb` en sede requiere JavaScript para poblar la tabla (66 trámites).
- Sin boletín autonómico en `ccaa_history` (`bocm_count: 0`); BOCCE es la fuente paralela.
- Ciudad autónoma (único municipio).

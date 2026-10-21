# Lugo — investigación portal ayuntamiento

Municipio: **Lugo** (`lugo`) — Galicia, provincia Lugo.  
INE: **27028**. Sin boletín autonómico asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://www.lugo.gal/portal/ | Plataforma IMC (tablón, catálogo trámites, registro). |
| Tablón de anuncios | https://www.lugo.gal/portal/tablonanuncios | iframe → `POST /portal/publicaciones` (`TipoPublicarEn.TablonElectronico`). |
| Catálogo trámites | https://www.lugo.gal/portal/tramites | Listado HTML; detalle vía `verDetalleTramite(codigo, praId)` (POST). |
| Web corporativa | https://concellodelugo.gal/ | Drupal 7: noticias y área de urbanismo. |
| Planeamiento (web) | https://concellodelugo.gal/es/actuaciones/planeamiento-gestion-y-disciplina-urbanistica | Descripción de competencias (planeamiento, gestión, disciplina). |
| Urbanismo en Rede | https://concellodelugo.gal/gl/actuacions/urbanismo-en-rede | Enlace al visor histórico Red.es. |
| Visor Urbanismo en Red | http://urbanismoenred.lugo.es/Visor/ | OpenLayers + WMS/WFS (visor municipal legacy). |
| Datos abertos PGOU | https://datosabertos.lugo.gal/es/e-transparencia-en-materias-de-urbanismo-obras-p%C3%BAblicas-y-medio-ambiente/e1-planes-de-ordenaci%C3%B3n-urbana-y-convenios-urban%C3%ADsticos | Transparencia planeamiento (indicadores, sin API CKAN estable en cloud). |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=27028 | JSON `query_document.php` (clases 14 PG, 13 desarrollo, 16 histórico). |
| SIOTUGA estado | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | PGOM aprobado 2011-04-29 (adaptado LOUG); enlace WMS por INE. |

## Expedientes / proyectos

- **Tablón sede:** ~300 anuncios; filtro urbanístico (expropiación, obras, exposición pública no electoral) vía POST paginado + detalle por `codigo` (PDF en `https://www.lugo.gal/publicacions/{uuid}.pdf`).
- **SIOTUGA:** PGOM vigente y **191** instrumentos de planeamiento de desarrollo (sectores SUNP, etc.) con fechas de aprobación y figura normativa; API `assets/inventario/query_document.php` con `token` de sesión.
- **Noticias Drupal:** búsqueda `search/node/urbanismo` (licencias, instrucciones, plan de choque).
- **No** hay expediente urbanístico abierto tipo Pozuelo (Drupal IP); la información normativa está en SIOTUGA + visor.

## Licencias

- **No** hay tablón ni dataset de licencias concedidas con dirección/fecha.
- La sede permite tramitar licencias y comunicaciones (noticia 12/2021: nueve procedimientos directos a Urbanismo); catálogo en `/portal/tramites` (búsqueda mayoritariamente interactiva).
- Estrategia adapter: páginas informativas de trámites + noticias que mencionan licencias + anuncios del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA: WMS por documento (`getIotpuWMS.php?codine=27028`) y visor cartográfico autonómico; capas por instrumento de planeamiento, no por expediente del tablón.
  - Urbanismo en Red (municipal): visor OpenLayers con capas WMS/WFS; sin API REST moderna ni enlace a códigos `COM/YYYY/NNN` del tablón.
- **Estrategia:** metadatos de planeamiento desde SIOTUGA; polígonos por expediente de licencia/anuncio no enlazables de forma determinista. El orquestador usará centroide municipal + jitter cuando falte `geom_geojson`.
- **Limitaciones:** tablón solo PDF; trámites sede requieren POST/JS; SIOTUGA exige cookie + `token` por sesión.

## Limitaciones técnicas

- Codificación sede: ISO-8859-1 en varias respuestas.
- Primera carga SIOTUGA/tablon: timeouts generosos (90 s).
- `queue claim` puede alterar otros campos de `queue.yaml` — al marcar `done`, parchear solo el slug `lugo`.

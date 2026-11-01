# Investigación portal — cinco municipios (slug BOCM compuesto)

**Slug:** `san-agustin-del-guadalix-pedrezuela-guadalix-de-la-sierra-venturada-y-cabanillas-de-la-sierra`  
**Fecha:** 2026-10-15  
**BOCM:** 1 aviso regional que cita conjuntamente los cinco ayuntamientos (planeamiento / corredor norte).

## Resumen

Entrada de cola generada por un **anuncio BOCM multi-municipio**. Cada municipio ya tiene adapter propio en el pipeline (`done` en cola). Este onboarding **no re-scrapea** portales nuevos: el adapter compuesto delega en los cinco adaptadores existentes y fusiona `proyectos.jsonl` / `licencias.jsonl` (mismo patrón que `mijas-alhaurin-el-grande`).

| Municipio | Slug individual | Web / sede | Adapter |
|-----------|-----------------|------------|---------|
| San Agustín del Guadalix | `san-agustin-del-guadalix` | sanagustindelguadalix.net + sede espublico | `san_agustin_del_guadalix.py` |
| Pedrezuela | `pedrezuela` | pedrezuela.info + sede espublico | `pedrezuela.py` |
| Guadalix de la Sierra | `guadalix-de-la-sierra` | guadalixdelasierra.com + eAdmin | `guadalix_de_la_sierra.py` |
| Venturada | `venturada` | venturada.org + sede espublico | `venturada.py` |
| Cabanillas de la Sierra | `cabanillas-de-la-sierra` | cabanillasdelasierra.es + sede | `cabanillas_de_la_sierra.py` |

## Fuentes del portal (por municipio)

Detalle en cada `data/municipios/<slug>/RESEARCH.md` individual. Patrones comunes en la zona norte de Madrid:

- **Transparencia / WordPress o Joomla** con PDFs de PGOU, NNSS, convenios y formularios de licencia.
- **Sede electrónica** (espublico gestiona o eAdmin Maggioli): tablón `/board/` cuando scrapeable; trámites informativos.
- **Planeamiento vectorial:** WFS SITCM Comunidad de Madrid (`sitcm:VPLA_V_AMBITO`) en cuatro de cinco municipios.

## Licencias

Agregación de filas informativas (formularios PDF, trámites sede, edictos tablón) de cada ayuntamiento. Sin listado único intermunicipal de concesiones georreferenciadas.

## Geometría / visor

- **geometry_status:** `partial` (heredado de miembros; San Agustín del Guadalix sin WFS municipal)
- **Fuentes:**
  - Pedrezuela, Guadalix de la Sierra, Venturada, Cabanillas: WFS `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO` filtrada por `DS_MUNICIPIO`
  - San Agustín del Guadalix: sin visor/GIS público enlazable (`unavailable` en slug individual)
- **Estrategia:** polígonos vía adapters miembros; filas sin geometría → centroide municipio + jitter en orquestador
- **Limitaciones:** slug compuesto no tiene portal único; IDs de filas conservan prefijo del municipio origen

## Limitaciones

- Duplicación lógica con slugs individuales ya en `done` (reconciliación en matching BOCM).
- Tiempo de ejecución ~5× (cinco scrapes secuenciales).
- SSL `insecure_ssl` en algunos miembros (Pedrezuela, Cabanillas, San Agustín .net).

## Paridad esperada

- `proyectos`: ok (suma de expedientes/PDFs/tablón/SITCM de los cinco)
- `licencias`: partial (trámites informativos)
- `with_geometry`: > 0 (ámbitos SITCM de 4 municipios)

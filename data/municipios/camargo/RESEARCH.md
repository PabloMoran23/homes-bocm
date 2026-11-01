# Camargo — investigación portal ayuntamiento

**Municipio:** Camargo (Cantabria)  
**Fecha:** 2026-11-01

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica (OpenSIAC) | https://sede.aytocamargo.es | Tablón información pública, trámites, registro |
| Tablón / edictos | https://sede.aytocamargo.es/opensiac/informacionpublica/infopublica.action | **Fuente principal** — grupos (Urbanismo, Edictos, …) con `infopublica_ver.action?id=` |
| Búsqueda tablón | `…/infopublica_search.action` | POST `edictos=OTROS`, `descripcionTipoTablon=Ayuntamiento de Camargo` |
| Trámites urbanismo | https://sede.aytocamargo.es/opensiac/informacionpublica/tramites_enter.action | Licencias obra/actividad/apertura (sin histórico de concesiones) |
| Web municipal | https://www.aytocamargo.es | Drupal — urbanismo, planos PGOU |
| Urbanismo | https://www.aytocamargo.es/urbanismo-medio-ambiente-servicios/urbanismo | Información de trámites y contacto |
| Planos ordenación PGOU | https://www.aytocamargo.es/urbanismo-medio-ambiente-servicios/urbanismo/planos-ordenacion | PDFs clasificación/calificación del suelo (1987 PGOU) |
| Datos abiertos | https://datos.aytocamargo.es | CKAN municipal (no dataset urbanístico estructurado) |
| BOC Cantabria | https://boc.cantabria.es | Publicaciones oficiales (p. ej. convenio UA A02.05 Valle Real, 2025) |

## Cómo se listan expedientes

- **OpenSIAC:** tabla HTML `listaPublicacionesDescripcion` + fecha + enlace `infopublica_ver.action?id=NNNN`. Grupo **Urbanismo** incluye convenios de planeamiento (p. ej. Unidad A02.05 Valle Real, oct-2025).
- **Detalle:** ficha con campos `Etiqueta`/`Descripcion` y descargas `infopublica_descargar.action` (PDF).
- **Índice completo:** ~487 publicaciones en `infopublica.action` (filtradas por regex urbanística en el adapter).
- **Web PGOU:** planos estáticos PDF en página de ordenación (respuesta lenta desde CI; documentado como semilla).

## Cómo se publican licencias

- **Tablón:** pocas entradas con texto “licencia” (p. ej. licencias taxi — excluidas como no urbanísticas).
- **Sede:** catálogo de trámites OpenSIAC (licencia obra, actividad, apertura inocua, etc.) sin listado histórico scrapeable.
- Estrategia adapter: páginas informativas de trámites + tablón filtrado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCAN WFS Cantabria: `https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer`
  - Capa: `Urbanismo:Sectores`
  - Filtro client-side: `Código_INE = 39016` / `Denominación_Municipio = Camargo` (20 sectores con polígono)
  - Visor regional: https://mapas.cantabria.es/ (SIUCAN)
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; intentar enriquecer filas del tablón por código UA/sector en título (`A02.05`, `SUNP-*`, …).
- **Limitaciones:**
  - Sin visor municipal enlazado a expedientes individuales del tablón.
  - Licencias no georreferenciadas en sede.
  - WFS en GML3 (no GeoJSON nativo).
  - Web `aytocamargo.es` con latencia alta desde algunos entornos.

## Limitaciones generales

- Municipio del valle de Camargo (~32k hab., sede Muriedas).
- OpenSIAC codificación `iso-8859-15`.
- Sin `boletin_source_id` en cola (0 entradas BOCM asociadas en CSV).
- Mezcla de anuncios administrativos en tablón — filtrados por regex.

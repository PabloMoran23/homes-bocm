# Castro-Urdiales — investigación portal ayuntamiento

**Municipio:** Castro-Urdiales (Cantabria)  
**Fecha:** 2026-10-29

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (ASP.NET / Micastro) | https://www.castro-urdiales.net | Portal principal |
| Urbanismo / Servicios Técnicos | https://www.castro-urdiales.net/servicios.aspx?vista=servicios-ciudadania&cod=urbanismo | Trámites, herramientas urbanísticas, enlaces a sede y AUCAN |
| Instrumentos vigentes | https://www.castro-urdiales.net/servicios-ciudadania/informacion/instrumentos-urbanisticos-existentes-vigentes | PDF estudio de detalle UE 1.26 |
| Catálogos urbanísticos | https://www.castro-urdiales.net/servicios-ciudadania/informacion/catalogos-urbanisticos | Catálogo edificaciones suelo rústico (PDF) |
| PMUS | https://www.castro-urdiales.net/servicios-ciudadania/informacion/pmus | Documentación PMUS + aprobación inicial / exposición pública |
| Cartografía | https://www.castro-urdiales.net/servicios-ciudadania/informacion/cartografia-ortofotos | Archivos RAR (cartografía municipal) |
| Sede electrónica | https://sedeelectronica.castro-urdiales.net/ | Maggioli ATM (Angular SPA); **certificado SSL caducado** |
| AUCAN (Gob. Cantabria) | https://aplicacionesweb.cantabria.es/aucan/public/zona/costaoriental/castrourdiales | PGOU y documentación regional |
| Archivo municipal | https://archivomunicipal.castro-urdiales.net/ | Patrimonio documental (no urbanismo operativo) |

## Cómo se listan expedientes

- **Sede (exposición pública):** enlace desde urbanismo apunta a la sede Maggioli para convenios, solicitudes de licencias e instrumentos en tramitación; la SPA **no** expone API/listado HTML scrapeable sin sesión.
- **Web municipal:** documentos en bloques `<ul class='download'>` con PDFs bajo `/recursosWEB/publicaciones/…` (instrumentos, PMUS, catálogos).
- **Noticias / actualidad:** sin canal dedicado a urbanismo en el listado reciente (mayoría administrativa/cultural).
- **BOC Cantabria:** publicaciones históricas (p. ej. modificación ordenanza URB/1347/2019); este municipio no tiene `boletin_source_id` en cola.

## Cómo se publican licencias

- **No hay tablón municipal scrapeable** en la web principal (a diferencia de otros ayuntamientos WP).
- **Sede Maggioli:** tramitación y, presumiblemente, edictos de exposición pública dentro de la sede (SPA).
- **Web:** solo **formularios/modelos** de solicitud (licencia urbanística, DR obras, apertura actividades, primera ocupación, etc.) — páginas informativas, no concesiones históricas.
- Estrategia adapter: filas informativas de trámites + enlace sede/AUCAN; sin listado de concesiones georreferenciadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCAN WFS Cantabria: `https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer`
  - Capa: `Urbanismo:Sectores`
  - Filtro client-side: `Código_INE = 39020` / `Denominación_Municipio = Castro Urdiales`
  - Sectores PGOU (p. ej. `SUNP-12`, `SUP-1`, …) con polígonos GML
  - Visor regional AUCAN + https://mapas.cantabria.es/
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; intentar enriquecer PDFs del ayto. si el título contiene código de sector (`SUNP-*`, `SUP-*`).
- **Limitaciones:**
  - Sede con SSL caducado (`sede_insecure_ssl: true`).
  - Sin visor municipal enlazado a expedientes de licencia individuales.
  - PMUS / estudios de detalle solo PDF, sin geometría vectorial en portal.
  - WFS sin `outputFormat=geojson` fiable; parseo GML3.

## Limitaciones generales

- Municipio costero (~32k hab.); pocos PDFs urbanísticos en web estática.
- Sede Maggioli ATM igual que otros municipios cantábricos/madrileños: sin tablón automatizable.
- Cartografía publicada como RAR (no GeoJSON).
- `bocm_count: 0` en cola — cruce BOCM no aplicable.

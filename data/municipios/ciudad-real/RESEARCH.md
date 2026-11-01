# Ciudad Real — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.ciudadreal.es |
| Urbanismo (hub) | https://www.ciudadreal.es/servicios-municipales/urbanismo.html |
| Documentación en trámite | https://www.ciudadreal.es/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/documentacion-en-tramite.html |
| Modificaciones PGOU | https://www.ciudadreal.es/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/modificaciones.html |
| Estudios de detalle | https://www.ciudadreal.es/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/instrumentos-de-desarrollo-y-complementarios/estudios-de-detalle.html |
| Sectores / UE | instrumentos-de-desarrollo-y-complementarios (sectores, unidades-de-ejecucion) |
| PGOU | https://www.ciudadreal.es/servicios-municipales/urbanismo/planificacion-y-operaciones-estrategicas/pgou-ciudad-real.html |
| Convenios urbanísticos | https://www.ciudadreal.es/ayuntamiento/convenios/convenios-urbanisticos-2.html |
| Licencias (info) | https://www.ciudadreal.es/servicios-municipales/urbanismo/servicio-de-licencias.html |
| Sede electrónica | https://www.ciudadreal.es/sede-electronica.html (formularios; sin tablón urbanístico tipo STA) |
| Registro telemático Diputación (SIGEM) | https://se3.dipucr.es:4443/SIGEM_AutenticacionWeb/ (trámites registro; no listado IP) |

CMS: **Joomla** (`item-page`, menús por secciones). Los expedientes de planeamiento se publican como **bloques de título + enlaces a PDF/ZIP** en HTML estático, no como API ni expediente numerado consultable.

## Listado de proyectos / planeamiento

- **Documentación en trámite**: títulos en mayúsculas (modificaciones PGOU, estudios de detalle, PAU UE-VCAR, etc.) con enlaces a `/documentos/urbanismo/planeamiento/*.pdf`.
- **Estudios de detalle / modificaciones**: mismos patrones; fechas en prefijo `YYYYMMDD_` del nombre de fichero o en anuncios DOCM.
- **Convenios**: PDFs bajo `/documentos/conveniosurbanismo/` (sectores S-MADR, UE-ALB2, etc.).
- **PGOU**: planos PDF en `/documentos/direcciongralplanificacion/pgouciudadreal/` y visor **Google My Maps** embebido (clasificación general, no por expediente).

No hay visor de expedientes con código ni sede STA con tablón de anuncios urbanísticos (comprobado `sede.ciudadreal.es` sin PTS_TABLON operativo desde el entorno del agente).

## Licencias de obra

- El ayuntamiento publica **memorias del servicio de licencias** (`/documentos/urbanismo/licencias/MEMORIA_*.pdf`) y formularios en urbanismo / sede.
- **No** hay listado público de licencias concedidas (fechas, direcciones) comparable al tablón de Madrid/Getafe.
- Estrategia del adapter: filas informativas de trámites + memorias (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Google My Maps del PGOU (`mid=1GAuHSHT-z5kGrAZk67O_LdAhKQeLpNk` en página PGOU); planos PDF raster en `/documentos/direcciongralplanificacion/`. No hay ArcGIS/WFS municipal con campo de expediente enlazado a cada actuación en trámite.
- **Estrategia:** el orquestador usará centroide municipal + jitter; no se implementa `_fetch_geometry` (sin join expediente ↔ polígono).
- **Limitaciones:** solo documentación PDF/ZIP; mapa PGOU no machine-readable por proyecto; sin coordenadas en tablón.

## Limitaciones generales

- Paginación irrelevante (pocas páginas semilla).
- SSL estándar en www.ciudadreal.es.
- Boletín regional: municipio sin `boletin_source_id` en cola (0 entradas BOCM en CSV).

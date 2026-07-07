# León — investigación portal ayuntamiento

**Municipio:** León (provincia León, Castilla y León)  
**BOCYL:** 19 entradas (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sede.aytoleon.es/eAdmin/Sede.do | Portal eAdmin (add4u) |
| Tablón de anuncios | https://sede.aytoleon.es/eAdmin/Tablon.do?action=inicioTablon | 5 tablones temáticos (695 anuncios totales) |
| Listado tablón | https://sede.aytoleon.es/eAdmin/Tablon.do?action=verAnuncios | HTML tabular con `verAnuncio&id=` |
| Tablón urbanismo | Sección `tablon_3` en verAnuncios | 6 anuncios (proyectos urbanización, estudios detalle, mod. PGOU) |
| Búsqueda tablón | POST `referenciaBusqueda` → verAnuncios | Filtra por término (p. ej. «CONVENIO URBANISTICO») |
| Urbanismo web | https://aytoleon.es/es/tu-ayuntamiento/normativas/Paginas/urbanismo.aspx | SharePoint: PGOU, modificaciones, convenios, IP |
| Catálogo trámites | https://sede.aytoleon.es/eAdmin/Registrar.do?action=inicioPortalTramites | 13 trámites «Obras y Urbanismo» |
| SiuCyL (JCyL) | http://www.jcyl.es/plau/ | Planeamiento regional (no enlazado a expedientes del ayto.) |

## Expedientes / proyectos

- **Tablón urbanismo (`tablon_3`):** HTML estático eAdmin; filas con título, periodo de publicación y enlace `Tablon.do?action=verAnuncio&id=…`. PDF vía `javascript:abrirOriginal('token')` → `ValidarDocumento.do`.
- **Tablón general:** búsqueda POST por términos urbanísticos (PGOU, convenio urbanístico, sector NC/ULD/PR, estudio detalle).
- **Web corporativa:** página SharePoint con ~69 PDFs en secciones PGOU, modificaciones en IP, convenios urbanísticos (IP y aprobados), documentos IP.
- **No hay** visor municipal de expedientes en curso sin certificado (Carpeta Ciudadana requiere identificación).

## Licencias de obra

- El tablón **no publica** concesiones de licencia (búsqueda «LICENCIA» → 0 resultados).
- Catálogo sede incluye trámites informativos: licencia urbanística (192), licencia ambiental (94), declaración responsable obra (39), cédula urbanística (172), etc.
- El adapter registra esas páginas de trámite como filas informativas (patrón Galapagar/Meco).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - SiuCyL / IDECyL WMS (`https://idecyl.jcyl.es/geoserver/urbanismo/wms`) — sectores y categorías de suelo a nivel autonómico, sin campo de enlace a expediente del ayuntamiento.
  - Web aytoleon.es — solo PDFs/planos, sin servicio WFS/ArcGIS municipal.
  - Sede eAdmin — tablón PDF sin coordenadas ni objectId GIS.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [42.5987, -5.5671]` en manifest).
- **Limitaciones:** no hay visor urbanístico municipal público ni dataset GeoJSON por expediente; la cartografía sectorial de JCyL no es consultable por código de expediente del tablón.

## Limitaciones técnicas

- Búsqueda del tablón devuelve HTML reducido (~214 KB) cuando no hay coincidencias; términos genéricos como «LICENCIA» dan 0 filas.
- `tipoTablon=3` en query string no filtra en servidor; hay que parsear la sección `id="tablon_3"`.
- Encoding sede: ISO-8859-1 en respuestas eAdmin.
- PDFs SharePoint usan rutas relativas bajo `/es/tu-ayuntamiento/corporación/secretaria/…`.

## Adapter

`municipio.adapters.leon:LeonAyuntamientoAdapter` — tablón urbanismo + búsqueda + PDFs web + trámites sede.

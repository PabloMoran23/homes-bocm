# León — investigación portal ayuntamiento

Municipio: **León** (`leon`) — Castilla y León / BOCYL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://aytoleon.es |
| Urbanismo (SharePoint) | https://aytoleon.es/es/tu-ayuntamiento/normativas/Paginas/urbanismo.aspx |
| Sede electrónica | https://sede.aytoleon.es/eAdmin/Sede.do |
| Tablón de anuncios | https://sede.aytoleon.es/eAdmin/Tablon.do?action=inicioTablon |
| Listado tablón | https://sede.aytoleon.es/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo trámites | https://sede.aytoleon.es/eAdmin/Registrar.do?action=listadoEntradas |

## CMS / tecnología

- **Portal corporativo:** Microsoft SharePoint (aytoleon.es) con acordeones de documentación urbanística (PDF/ZIP/7z en rutas `/es/tu-ayuntamiento/corporación/secretaria/`).
- **Sede electrónica:** eAdmin **add4u** (mismo patrón que San Lorenzo de El Escorial, Meco, Colmenar Viejo): tablón HTML con `verAnuncio&id=<hex>`, documentos firmados vía `ValidarDocumento.do?id_Documento=...`.

## Proyectos / planeamiento

### Portal urbanismo (principal)

La página de urbanismo publica de forma estática:

- PGOU (tomos I–VII en ZIP)
- Modificaciones PGOU en información pública y aprobadas
- Convenios urbanísticos (IP y definitivos)
- Estudios de detalle, planes parciales, proyectos de actuación/urbanización
- Gestión urbanística (estatutos JC, determinaciones de urbanización, etc.)

**Formato:** enlaces directos a PDF/ZIP/7z en SharePoint. No hay API JSON; el adapter parsea `href` con extensión documental y filtra rutas `PGOU`, `Modificaciones PGOU`, `Convenios Urban`, `Documentos Planeamiento`, `Documentos Gestin Urban`.

### Tablón sede (complementario)

- ~669 anuncios en listado completo; sub-tablones por categoría (anuncios, empleo, urbanismo, etc.).
- Búsqueda POST a `Tablon.do?action=verAnuncios` con `referenciaBusqueda` (PLANEAMIENTO, PGOU, SECTOR, LICENCIA, etc.).
- Filas HTML: `verAnuncio&id`, título en `<td width="50%">`, periodo `dd/mm/yyyy - dd/mm/yyyy`, PDF opcional vía `abrir('token')`.

Anuncios urbanísticos recientes en tablón: estudios de detalle, modificaciones PGOU, licencias ambientales.

## Licencias de obra

- **No hay listado público de concesiones** de licencia de obras (solo solicitudes/trámites).
- Tablón: algunas **licencias ambientales** publicadas como anuncios.
- Trámites informativos en sede (`Registrar.do?action=infoTramite&tipoReg=`):
  - 108 — Licencia de Obras
  - 192 — Licencia Urbanística
  - 39 — Declaración responsable ejecución de obra
  - 188 — Declaración responsable primera ocupación
  - 94, 107, 109, 100 — Licencias ambientales/apertura/comunicaciones
  - 172 — Cédula urbanística
  - 106 — Segregación/agrupación
  - 112 — Registro ITE
  - 70 — Exposición pública (alegaciones)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal público enlazado a expedientes. El PGOU se publica en PDF/ZIP sin servicio ArcGIS/WFS del ayuntamiento.
- **Alternativa regional (no usada en adapter):** SiuCyL / IDECyL (`https://idecyl.jcyl.es/geoserver/urbanismo/wms`) ofrece capas de planeamiento a nivel autonómico, sin enlace por código de expediente municipal.
- **Estrategia:** Sin `geom_geojson`; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** Documentación solo PDF; sin coordenadas ni objectId consultable por expediente.

## Limitaciones

- Convenios genéricos en tablón (deportes, asociaciones) se excluyen por filtro de keywords urbanísticas.
- SharePoint: títulos de enlace a veces son nombres de archivo (encoding URL).
- Tablón completo es pesado (~669 filas); el adapter usa búsquedas dirigidas + página urbanismo.
- Licencias de obra: solo trámites informativos + licencias ambientales del tablón.

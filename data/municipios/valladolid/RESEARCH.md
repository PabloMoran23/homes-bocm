# Valladolid — investigación portal ayuntamiento

Municipio: **Valladolid** (`valladolid`) — Castilla y León, provincia Valladolid. Boletín: **BOCYL** (`bocyl`, 35 entradas).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal municipal | https://www.valladolid.gob.es |
| Sede electrónica | https://sede.valladolid.es |
| Tablón — Anuncios/Edictos | https://www.valladolid.gob.es/es/tablon-oficial/ayuntamiento-valladolid/anuncios-edictos |
| Búsqueda tablón (GET) | `/es/tablon-oficial/ayuntamiento-valladolid-tablon-oficial.buscar` |
| Carpeta contribuyente (STA) | https://contribuyente.valladolid.es/sta/CarpetaPublic/ |
| Portal GIS municipal | https://www10.ava.es/cartografia/inicio_gis_valladolid.html |
| Visor DROUS (obras) | https://gisava.valladolid.es/portal/apps/webappviewer/index.html?id=c6d3c10df19b4e55a7badc021b51cfe1 |
| PLAU-i (CyL, IP planeamiento) | https://servicios.jcyl.es/PlanPublica/lmuni_plai.do?provincia=47 |
| Urbanismo en red | http://www10.ava.es/Visor/ |

## CMS / tecnología

- **Proxia Premium** (Divisa Informática) en `valladolid.gob.es`: listados HTML (`cmContentList`), formulario de búsqueda con filtros `S_REMITENTE_min`, `S_TEMA_EDICTO_min`, `text`, fechas `ACTIVATIONDATE_*`.
- Paginación: `/anuncios-edictos.relaciones,{offset},{pageSize}`.
- Cada anuncio enlaza a ficha (`…-tablon-oficial/…`) y PDF en `.ficheros/`.
- Sede: **OpenCMS**; trámites urbanismo en menú pero sin dataset público embebido (requiere identificación para expedientes).

## Proyectos / expedientes urbanísticos

**Fuente principal:** PLAU-i (Junta CyL) — listado paginado de instrumentos de planeamiento del municipio (`municipio=186`, `provincia=47`).

**Fuente complementaria:** tablón oficial filtrado por temas de urbanismo:

- `ANUNCIO DE INFORMACIÓN PÚBLICA`
- Búsqueda texto: `planeamiento`, `urbanismo`

Remitentes habituales: Sección de Planeamiento, Gestión Urbanística, Gerencia de Urbanismo, Servicio Control Legalidad Urbanística.

**Formato:** HTML + PDF; metadatos en `<dl class="features modelEdicto">` (fecha publicación `pval-s-fecha-publicacion`). La paginación `.relaciones` del tablón devuelve HTTP 500 (no usada).

## Licencias de obra

**Fuente principal:** capas **DROUS** en ArcGIS Enterprise (`gisava.valladolid.es`):

| Año | FeatureServer | Registros (jul 2026) |
|-----|---------------|----------------------|
| 2026 | `SDE_Drous_2026/FeatureServer/7` | ~3.039 |
| 2025 | `SDE_Drous_2025/FeatureServer/6` | ~5.662 |

Campos útiles: `JOIN_NUMER` (expediente, p. ej. `2026/DME_01/000684`), `FECHA` / `FECHA_NUM`, `EMPLAZAMIE`, `OBJETO_DRO`, `DISTRITO_T`, `REF_CATAST`. Geometría: polígono parcela (`esriGeometryPolygon`), consultable con `f=geojson&outSR=4326`.

**Sede:** catálogo de trámites «URBANISMO, LICENCIA DE OBRAS Y ACTIVIDADES» (páginas informativas, sin listado de concesiones).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **Licencias:** ArcGIS FeatureServer DROUS (`returnGeometry=true`, `f=geojson`, `outSR=4326`) — polígono por expediente de obra.
  - **Proyectos:** PGOU/PLAU-i y visores temáticos (`www10.ava.es/Visor/`) muestran planeamiento zonal, no delimitación por expediente del tablón.
- **Estrategia adapter:**
  - Licencias: paginar query ArcGIS por año configurado; rellenar `geom_geojson` + centroide.
  - Proyectos: PLAU-i paginado + búsquedas tablón (sin geometría por expediente).
- **Limitaciones:** tablón/IP son PDF sin georreferencia; DROUS no enlaza con códigos de expedientes de planeamiento del tablón; PLAU-i requiere sesión/formulario HTML.

## Limitaciones generales

- Tablón mezcla tráfico, empleo público, hacienda — requiere filtro por remitente/tema/regex; búsquedas pueden hacer timeout (adapter tolera fallos).
- Paginación tablón `.relaciones` devuelve HTTP 500.
- Sin API REST del tablón; scrape HTML determinista.
- DROUS histórico voluminoso (>20k features 2023–2026); adapter limita años en `manifest.config.drous_years`.
- `contribuyente.valladolid.es` (STA) exige login para expedientes personales.

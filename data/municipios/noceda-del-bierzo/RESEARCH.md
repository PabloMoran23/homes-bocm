# Noceda del Bierzo — investigación portal ayuntamiento

**Fecha:** 2026-09-26  
**Slug:** `noceda-del-bierzo`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Noceda del Bierzo publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://nocedadelbierzo.es | WordPress (CityGov + Elementor) | Trámites, ordenanzas fiscales (ICIO), anuncios/bandos, enlace a sede |
| Sede electrónica | https://nocedadelbierzo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (`/board/`), información (`/info.0`), catálogo trámites (`/dossier`) |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Archivo aprobado prov. 24, muni. **102** (código «102-NOCEDA DEL BIERZO» en tablón) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumento de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
- **Filtro:** `c_mun = '24102'` (INE 24102 — **Noceda del Bierzo**; no confundir con 24104 = Las Omañas)
- Instrumento vigente: **Normas Subsidiarias de Planeamiento Municipal** (NS), polígono MultiPolygon WGS84

### 2. PlanPublica CYL — archivo aprobado

- **Listado:** https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=102
- **Documentos:** NS (`cDocId=280311`, `24102-PU-A19910709-280311`); planeamiento histórico (`cDocId=282495`, `24102-PU-20050620-282495`)

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://nocedadelbierzo.sedelectronica.es/board/
- **Formato:** enlaces `preview-document/{uuid}` (HTML espublico)
- **Ejemplo urbanismo:** bando «Títulos de Propiedad Concentración Parcelaria»

### 4. Web — anuncios y ordenanzas

- https://nocedadelbierzo.es/anuncios-y-bandos/
- https://nocedadelbierzo.es/ordenanzas-y-reglamentos/ (ordenanza fiscal nº 3 construcciones / ICIO)

## Fuentes de licencias

1. **Páginas informativas** — trámites (`/tramites/`, sección Urbanismo y Vivienda → sede), ordenanza fiscal de construcciones
2. **Tablón sede** — sin anuncios de concesión de licencia en la ventana actual (solo bandos administrativos)
3. **Catálogo sede** (`/dossier`) — formularios de solicitud (respuesta lenta/vacía en el entorno del agente)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono del ámbito municipal (NS)
  - Sin sectores ni planes parciales en WFS para este municipio (consulta 2026-09-26)
- **Estrategia:** descarga WFS por `c_mun='24102'`; anuncios del tablón usan polígono municipal si no hay sector
- **Limitaciones:** licencias sin geolocalización; sin visor urbanístico municipal propio; geometría = instrumento de planeamiento (NS), no parcelas de expedientes

## Limitaciones

- Catálogo `/dossier` no respondió de forma fiable en el entorno del agente (timeout)
- Tablón con pocos anuncios; concentración parcelaria sin geometría parcelaria en GIS público
- Licencias sin geolocalización en fuentes públicas

## Estrategia adapter

1. WFS IDECyL → proyecto instrumento con `geom_geojson`
2. Semillas PlanPublica + web → proyectos de planeamiento
3. Tablón espublico → proyectos (concentración parcelaria, etc.)
4. Páginas trámite/ordenanzas → licencias informativas

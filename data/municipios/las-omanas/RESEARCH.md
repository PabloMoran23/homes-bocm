# Las Omañas — investigación portal ayuntamiento

**Fecha:** 2026-09-21  
**Slug:** `las-omanas`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Las Omañas publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytolasomanas.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística, trámites/licencias, enlaces PlanPublica CYL |
| Sede electrónica | https://aytolasomanas.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (`/dossier.0`), transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Archivo aprobado: NUT León (cDocId=301592); prov. 24, muni. 104 |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumento de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0), `plau_cyl_sectores` (0)
- **Filtro:** `c_mun = '24104'` (INE 24104)
- Instrumento: **Normas Urbanísticas Territoriales** con polígono MultiPolygon WGS84

### 2. PlanPublica CYL — archivo aprobado

- **URL:** https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=104
- **Documento:** NORMAS URBANÍSTICAS TERRITORIALES (`cDocId=301592`, código `24000-PU-20240621-301592`)
- PDF guía con memorias, normativa, catálogo y documentación gráfica (NUT provincial aplicable al municipio)

### 3. Web OpenCms — normativa

- **URL:** https://www.aytolasomanas.es/ayuntamiento/urbanismo/
- Enlaces a planeamiento CYL en información pública y archivo aprobado
- Sin expedientes municipales propios publicados como listado

### 4. Sede electrónica — tablón de anuncios

- **URL:** https://aytolasomanas.sedelectronica.es/board
- **Formato:** tabla HTML espublico
- **Estado:** vacío (sin anuncios de urbanismo en la ventana actual)

### 5. Transparencia sede

- **URL:** https://aytolasomanas.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** — 0 documentos

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura
2. **Tablón sede** — sin anuncios de licencias en la ventana actual
3. **Catálogo sede** (`/dossier.0`) — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono del ámbito municipal (NUT)
  - Sin sectores ni planes parciales en WFS para este municipio
- **Estrategia:** descarga WFS por `c_mun='24104'`; expedientes del tablón (si aparecen) usan centroide municipal + jitter
- **Limitaciones:** licencias sin geolocalización; sin visor urbanístico municipal propio; solo instrumento territorial (NUT) con geometría, sin sectores de desarrollo

## Limitaciones

- Tablón sede vacío en el momento de la investigación
- Transparencia urbanismo sin documentos
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio (solo WFS regional IDECyL)
- Planeamiento municipal = NUT provincial (no PGOU propio con sectores)

## Estrategia adapter

1. WFS IDECyL → proyecto instrumento con `geom_geojson`
2. Semillas PlanPublica + normativa web → proyectos de planeamiento
3. Páginas trámite OpenCms → licencias informativas
4. Tablón espublico → proyectos/licencias cuando haya anuncios

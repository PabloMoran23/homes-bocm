# Santas Martas — investigación portal ayuntamiento

**Fecha:** 2026-10-17  
**Slug:** `santas-martas`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Santas Martas (provincia de León, Castilla y León) publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytosantasmartas.es | OpenCms (`es.samdipuleon.templates`, Diputación León) | Trámites/licencias, tablón web, enlaces sede |
| Sede electrónica | https://aytosantasmartas.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (`/dossier.0`), transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | PLAU/PLAI provincia 24, municipio 160 |

**Nota:** `www.santasmartas.es` redirige a la sede pero el host `santasmartas.sedelectronica.es` responde «Sede Electrónica Indeterminada»; la sede operativa es `aytosantasmartas.sedelectronica.es`.

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumentos y sectores

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0), `plau_cyl_sectores` (1)
- **Filtro:** `c_prov_mun = '24160'` (INE 24160; el filtro `c_mun` devuelve HTTP 400 en estas capas)
- Instrumento: **Normas Urbanísticas Municipales** (NUM, aprobación 2012, BOCYL 2013)
- Sector: **SM Calle Nueva** (`SU-NC-OG`, suelo urbano no consolidado) con polígono WGS84

### 2. PlanPublica CYL — archivo aprobado

- **Archivo aprobado:** https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=160
- **Info pública:** https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=160
- **Índice NUM:** https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=289831
- Documentos históricos: plan parcial 1973, NUM 2012, anulaciones

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://aytosantasmartas.sedelectronica.es/board
- **Formato:** tabla HTML espublico (~10 anuncios)
- **Estado (oct 2026):** censos electorales, edictos de cobranza; sin licencias urbanísticas en ventana actual

### 4. Web OpenCms — trámites

- **Trámites:** https://www.aytosantasmartas.es/ayuntamiento/tramites-solicitudes/
- Páginas de licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura
- Sin sección `/urbanismo/` dedicada (404)

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura
2. **Tablón sede** — sin anuncios de licencias en la ventana actual
3. **Catálogo sede** (`/dossier.0`) — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono del ámbito NUM municipal
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — sector `SU-NC-OG` (SM Calle Nueva)
  - Visor JCyL enlazado desde PlanPublica (`f_mapa` en metadatos WFS); sin query ArcGIS municipal propia
- **Estrategia:** descarga WFS por `c_prov_mun='24160'`; enriquecimiento por código de sector en título; expedientes del tablón sin GIS usan centroide municipal + jitter
- **Limitaciones:** sin visor urbanístico municipal; licencias sin polígono; filtro `c_mun` no usable en GeoServer para este municipio
- **Límite municipal (validación pipeline):** IGN OGC API sin coincidencia exacta para «Santas Martas»; se usa el polígono NUM de IDECyL (`plau_cyl_instrumentos_ambito`, `c_prov_mun=24160`) en `manifest.yaml` → `geometry.validation.municipal_boundary`

## Limitaciones generales

- OpenCms alojado en infraestructura Diputación León (respuestas lentas desde CI)
- `/dossier.0` puede redirigir en bucle; el adapter tolera fallo del catálogo
- Tablón sede: ventana corta, sin API JSON
- Sin datos abiertos locales con geometría de expedientes

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (instrumento + sector)
2. PLAU JCyL → semillas de planeamiento aprobado
3. Tablón espublico → proyectos/licencias filtrados por palabras clave
4. Páginas trámite web + catálogo sede → licencias informativas

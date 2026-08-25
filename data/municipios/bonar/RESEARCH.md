# Boñar — investigación portal ayuntamiento

**Fecha:** 2026-08-25  
**Slug:** `bonar`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Boñar publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytobonar.es | OpenCms (`es.samdipuleon.templates`) | Urbanismo, NUM (PDF BOCYL 2014), plan parcial PORMASOL (4 PDFs) |
| Sede electrónica | https://aytobonar.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, trámites (Licencias de Obras) |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Archivo aprobado NUM (provincia 24, municipio 021) |

**Nota:** `bonar.es` / `bonar.sedelectronica.es` no corresponden a este municipio (sede indeterminada). Dominios correctos: `aytobonar.es` y `aytobonar.sedelectronica.es`.

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y ámbito NUM

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (9), `plau_cyl_instrumentos_ambito` (1 NUM)
- **Filtro:** `n_mun = 'Boñar'` / `c_mun = '24021'`
- GeoJSON WGS84 con polígonos de sectores (SU-1, SU-2, SSUNC-1…7) y ámbito NUM

### 2. Web OpenCms — normativa y plan parcial

- **Urbanismo:** https://www.aytobonar.es/ayuntamiento/urbanismo/
- **NUM:** `BONAR-BOCYL-D-10112014-NNUU.pdf`
- **Plan parcial PORMASOL:** normativa, estado actual, sectores, ordenación (PDFs en `/export/sites/aytobonar/galerias/descargas/NNUU/`)

### 3. Junta CYL PlanPublica

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=021`
- Información pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=021` (sin documentos activos al investigar)

### 4. Sede electrónica — tablón de anuncios

- **URL:** https://aytobonar.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (preview-document)
- Ventana corta (~10 anuncios); incluye impacto ambiental, inmatriculación, bandos periurbanos
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

## Fuentes de licencias

1. **Citizen service sede** — Licencias de Obras (`/citizen-service/7cbb9d76-cae3-438a-8988-8bca7f3d01fe`)
2. **Web** — solicitud general con enlace al catálogo de procedimientos en sede
3. **Tablón sede** — anuncios puntuales cuando mencionan licencias/autorizaciones

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`: SU-1, SU-2, SSUNC-1…7)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono ámbito NUM municipal
- **Estrategia:** descarga WFS por municipio (`n_mun='Boñar'`); enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** plan parcial PORMASOL solo en PDF (sin capa WFS); licencias sin geolocalización; sin visor urbanístico municipal propio; `/dossier` puede timeout en CI

## Limitaciones

- Tablón sede: ventana corta, sin API
- Plan parcial PORMASOL no indexado en IDECyL WFS (solo PDFs web)
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio (solo WFS regional IDECyL)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (10 features: 9 sectores + 1 NUM)
2. Semillas web (urbanismo PDFs, PlanPublica) → proyectos de planeamiento
3. Tablón espublico → proyectos/licencias filtrados
4. Páginas trámite sede/web → licencias informativas

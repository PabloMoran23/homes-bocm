# Cimanes del Tejar — investigación portal ayuntamiento

**Fecha:** 2026-09-13  
**Slug:** `cimanes-del-tejar`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Cimanes del Tejar (León) publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytocimanesdeltejar.es | OpenCms (`es.samdipuleon.templates`, Dip. León) | Normativa urbanística, trámites/licencias, enlaces JCyL |
| Sede electrónica | https://cimanesdeltejar.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (`/dossier`), transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 055) |

Municipio compuesto (Alcoba de la Ribera, Azadón, Cimanes del Tejar, Secarejo, Velilla de la Reina, Villarroquel).

## URLs base y páginas semilla

- **Inicio:** https://www.aytocimanesdeltejar.es/
- **Urbanismo:** https://www.aytocimanesdeltejar.es/ayuntamiento/urbanismo/
- **Tablón (sede):** https://cimanesdeltejar.sedelectronica.es/board
- **Trámites sede:** https://cimanesdeltejar.sedelectronica.es/dossier
- **Licencia urbanística (web):** https://www.aytocimanesdeltejar.es/ayuntamiento/tramites-solicitudes/licencias-urbanisticas-ambientales-apertura/licencia-urbanistica.html
- **PLAI JCyL:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=055`
- **PLAU JCyL:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=055`
- **Archivo NUT:** `openDocuIndice.do?cDocId=301592` — Normas Urbanísticas Territoriales

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumentos de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas consultadas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0), `plau_cyl_sectores` (0)
- **Filtro:** `n_mun = 'Cimanes del Tejar'`
- GeoJSON WGS84 (`srsName=EPSG:4326`) con polígono del instrumento NUT

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://cimanesdeltejar.sedelectronica.es/board
- **Formato:** HTML espublico con enlaces `preview-document/{uuid}` (sin tabla completa en ventana actual; parser de enlaces)
- Anuncios recientes: subvenciones (no urbanismo); categoría Urbanismo cuando hay expedientes activos

### 3. Web OpenCms — normativa y enlaces JCyL

- Página urbanismo enlaza a PLAI/PLAU de JCyL (provincia 24, municipio 055)
- Sin visor urbanístico municipal propio

### 4. PlanPublica JCyL

- **Archivo aprobado:** 1 documento indexado — *Normas Urbanísticas Territoriales* (`cDocId=301592`)

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura (misma estructura OpenCms Dip. León)
2. **Tablón sede** — anuncios puntuales cuando mencionan licencias
3. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono del ámbito municipal (NUT)
  - IDECyL WFS `plau_cyl_sectores` / `plau_cyl_planes_parciales` — sin features para este municipio
- **Estrategia:** descarga WFS por municipio (`n_mun='Cimanes del Tejar'`); enriquecimiento por código de sector en título cuando aplique; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** sin sectores urbanísticos digitalizados en WFS; licencias y expedientes puntuales sin polígono enlazable; sin visor urbanístico municipal; consulta expedientes sede requiere login; planeamiento publicado principalmente como PDFs en JCyL

## Limitaciones

- Tablón sede: ventana corta (~2 anuncios en sept. 2026), sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Municipio compuesto (6 núcleos) sin capas sectoriales en IDECyL

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (NUT)
2. Tablón espublico → proyectos/licencias filtrados por regex
3. Páginas trámite OpenCms → licencias informativas
4. Semillas urbanismo + PlanPublica JCyL → proyectos de planeamiento

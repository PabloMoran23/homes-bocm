# Fresno de la Ribera — investigación portal ayuntamiento

**Fecha:** 2026-09-16  
**Slug:** `fresno-de-la-ribera`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Fresno de la Ribera (Zamora, Castilla y León) publica urbanismo en **dos portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://fresnodelaribera.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (~10 filas), trámites, transparencia |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | NUM aprobada (2005), sectores SUR y capas WFS |

No hay web corporativa activa (`fresnodelaribera.es` / `www.fresnodelaribera.es` no responden).

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y NUM

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_sectores` (4 sectores SURD.so.1–4)
- **Filtro:** `n_mun = 'Fresno de la Ribera'`, `c_mun = 49076`
- Polígonos WGS84 (`srsName=EPSG:4326`) con metadatos de sector y enlace documental

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://fresnodelaribera.sedelectronica.es/board/
- **Formato:** tabla HTML espublico con enlaces `preview-document/`
- Contenido reciente: plenos, calendario fiscal, censos INE — sin anuncios urbanísticos en ventana actual

### 3. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=076`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=076`
- NUM: `openDocuIndice.do?cDocId=282499` (aprobación 2005-05-25, BOCYL 2005-06-23)
- Documento complementario: `openDocuIndice.do?cDocId=282625`

### 4. BOCYL (referencia externa)

- 1 proyecto parseado en `projects.json` (no re-parseado en este adapter)

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales si mencionan licencias/obra (ventana corta, sin urbanismo reciente)
2. **Sede trámites** (`/dossier`) — catálogo de trámites (sin histórico de concesiones)
3. **Páginas informativas** — tablón y dossier como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 4 polígonos (SURD.so.1–4, suelo urbanizable residencial)
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — ámbito NUM (Normas Urbanísticas Municipales)
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Fresno de la Ribera'`); enriquecimiento por coincidencia de título/sector en tablón; resto centroide municipal + jitter
- **Limitaciones:** sin visor urbanístico municipal; tablón sin GIS enlazable; licencias sin geolocalización; consulta de expedientes en sede requiere identificación

## Limitaciones

- Sin web corporativa accesible
- Tablón sede: ventana corta (~10 anuncios), sin API
- Licencias sin geolocalización en fuentes públicas
- Sin planes parciales en WFS (solo NUM + sectores de desarrollo)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados por keywords
3. Semillas Junta CYL (PLAI/PLAU + NUM) → proyectos de planeamiento
4. Páginas informativas sede → licencias (trámites, sin concesiones históricas)

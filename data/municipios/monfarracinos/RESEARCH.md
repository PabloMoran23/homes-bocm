# Monfarracinos — investigación portal ayuntamiento

**Fecha:** 2026-08-08  
**Slug:** `monfarracinos`  
**BOCYL regional (referencia):** 6 filas

## Resumen

Monfarracinos publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://monfarracinos.es | WordPress (instalación reciente, casi vacía) | Sin secciones de urbanismo publicadas; solo post por defecto |
| Sede electrónica | https://monfarracinos.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (~10 filas), trámites, transparencia |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | Planeamiento aprobado (c_mun=49122) y capas WFS de sectores |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (2), `plau_cyl_sectores` (19)
- **Filtro:** `n_mun = 'Monfarracinos'`, `c_mun = 49122`
- Incluye **Plan Regional Zamora Norte** (desarrollo industrial) y sectores SUR 01–06B con polígonos WGS84

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://monfarracinos.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Anuncios recientes con interés urbanístico: autorización ambiental Data Center Zamora, ordenanza tasa servicios urbanísticos

### 3. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=122`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=122`
- Documento NUM: `openDocuIndice.do?cDocId=281834`

### 4. BOCyL / BOP (referencia externa)

- Plan Regional Zamora Norte y proyecto de urbanización publicados en BOCyL 2024–2025 (no re-parseados; ya en `projects.json`)

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales si mencionan licencias/obra
2. **Sede trámites** (`/dossier`) — catálogo de trámites (sin histórico de concesiones)
3. **Páginas informativas** — tablón y dossier como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 19 polígonos (SUR 01, SUR 02, …)
  - IDECyL WFS `plau_cyl_planes_parciales` — Plan Regional Zamora Norte
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — Normas Urbanísticas Municipales
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Monfarracinos'`); enriquecimiento por coincidencia de título/sector en tablón; resto centroide municipal + jitter
- **Limitaciones:** web municipal sin visor; licencias y anuncios del tablón sin GIS enlazable; consulta de expedientes en sede requiere identificación

## Limitaciones

- Web `monfarracinos.es` recién migrada a WordPress sin contenido urbanístico
- Tablón sede: ventana corta (~10 anuncios), sin API
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados por keywords
3. Semillas Junta CYL (PLAI/PLAU) → proyectos de planeamiento
4. Páginas informativas sede → licencias (trámites, sin concesiones históricas)

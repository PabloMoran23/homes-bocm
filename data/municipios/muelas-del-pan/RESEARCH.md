# Muelas del Pan — investigación portal ayuntamiento

**Fecha:** 2026-09-25  
**Slug:** `muelas-del-pan`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Muelas del Pan (Zamora, CYL; anejos Cerezal de Aliste, Ricobayo, Villaflor) publica urbanismo en:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.ayto-muelasdelpan.com | HTML estático | Tablón urbanismo histórico (hasta 2018); normativas redirigen a sede |
| Sede electrónica | https://ayto-muelasdelpan.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, transparencia (normas urbanísticas), trámites `/dossier` |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | NUM aprobada 2003, sectores S.U.N.C. y plan parcial |

Desde 01/04/2018 el tablón de urbanismo solo se publica en la sede electrónica.

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (1), `plau_cyl_sectores` (4)
- **Filtro:** `n_mun = 'Muelas del Pan'`, `c_mun = 49135`
- Incluye NUM y sectores urbanísticos con polígonos WGS84

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://ayto-muelasdelpan.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Anuncios recientes: bandos de limpieza de terrenos, convocatorias pleno; histórico urbanismo en web municipal

### 3. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=135`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=135`
- Documento NUM: `openDocuIndice.do?cDocId=281831`

### 4. Transparencia sede — normas urbanísticas

- https://ayto-muelasdelpan.sedelectronica.es/transparency/c7a77dba-7233-4ce0-8f01-30c136dc94d7/

## Fuentes de licencias

1. **Tablón sede** — anuncios si mencionan licencias/obra/comunicación previa
2. **Sede trámites** (`/dossier`) — catálogo de trámites (sin histórico de concesiones)
3. **Páginas informativas** — tablón y dossier como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 4 polígonos (S.U.N.C. núcleos)
  - IDECyL WFS `plau_cyl_planes_parciales` — 1 plan parcial
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — Normas Urbanísticas Municipales
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Muelas del Pan'`); enriquecimiento por coincidencia de título en tablón; resto centroide municipal + jitter
- **Limitaciones:** sin visor urbanístico municipal propio; licencias y anuncios del tablón sin GIS enlazable; expedientes individuales en sede requieren identificación

## Limitaciones

- Tablón sede: ventana corta de anuncios visibles, sin API
- Licencias sin geolocalización en fuentes públicas
- Web histórica con PDFs de tablón antiguo (no scrapeados en detalle; semilla documental)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados por keywords
3. Semillas Junta CYL (PLAI/PLAU) y transparencia → proyectos de planeamiento
4. Páginas informativas sede → licencias (trámites, sin concesiones históricas)

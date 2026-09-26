# Granja de Moreruela — investigación portal ayuntamiento

**Fecha:** 2026-09-18  
**Slug:** `granja-de-moreruela`  
**BOCyL regional (referencia):** 1 fila

## Resumen

Granja de Moreruela (Zamora, CYL) publica urbanismo en **dos portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://granjademoreruela.sedelectronica.es | espublico gestiona (Wicket) | Tablón vacío; transparencia con sección urbanismo (0 docs) |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | DSU aprobada 1988 (cDocId=280531, c_mun=49091) |

No hay web corporativa accesible (`granjademoreruela.es` sin respuesta).

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumento de ámbito

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capa:** `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
- **Filtro:** `n_mun = 'Granja de Moreruela'`, `c_mun = 49091`
- Instrumento: **Delimitación de Suelo Urbano** (DSU), aprobación 1988-05-23
- Geometría: `MultiPolygon` en WGS84 (~41.2 km² de ámbito municipal)

### 2. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=091`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=091` (sin documentos)
- Documento DSU: `openDocuIndice.do?cDocId=280531`

**Nota:** el código PLAU `municipio=091` corresponde a Granja de Moreruela (INE 49091). El código `093` devuelve otro municipio.

### 3. Sede electrónica — tablón y transparencia

- **Tablón:** https://granjademoreruela.sedelectronica.es/board — `<tbody>` vacío
- **Transparencia:** https://granjademoreruela.sedelectronica.es/transparency — sección "7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (0)"
- Sin catálogo de trámites accesible (`/dossier` redirige sin contenido scrapeable)

## Fuentes de licencias

1. **Tablón sede** — vacío (sin anuncios de licencias)
2. **Transparencia** — sección urbanismo sin documentos publicados
3. **Páginas informativas** — tablón y transparencia como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 MultiPolygon (DSU municipal completa)
  - Sin sectores ni planes parciales en WFS (`plau_cyl_sectores` y `plau_cyl_planes_parciales`: 0 features)
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Granja de Moreruela'`, `srsName=EPSG:4326`); semillas PLAU heredan geometría del instrumento DSU por coincidencia de título
- **Limitaciones:** solo instrumento general (DSU 1988); sin visor municipal; tablón vacío; licencias sin GIS; expedientes puntuales no georreferenciados

## Limitaciones

- Sin web corporativa municipal
- Tablón sede vacío
- PLAI sin documentos en trámite
- Licencias sin geolocalización en fuentes públicas
- Municipio pequeño con planeamiento histórico (DSU 1988) sin desarrollo reciente publicado

## Estrategia adapter

1. WFS IDECyL → proyecto DSU con `geom_geojson` (MultiPolygon)
2. Semillas Junta CYL (PLAI/PLAU + índice DSU) → proyectos de planeamiento con geometría heredada
3. Páginas informativas sede (tablón, transparencia) → licencias (trámites, sin concesiones históricas)

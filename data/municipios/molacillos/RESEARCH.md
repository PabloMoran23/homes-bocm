# Molacillos — investigación portal ayuntamiento

**Fecha:** 2026-09-24  
**Slug:** `molacillos`  
**BOCyL regional (referencia):** 1 fila

## Resumen

Molacillos (Zamora, 239 hab.) publica gestión administrativa en **sede electrónica espublico**; el planeamiento normativo y la geometría de sectores están en **Junta de Castilla y León / IDECyL**.

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | http://molacillos.es | (sin respuesta HTTPS) | No usable; sin urbanismo |
| Sede electrónica | https://molacillos.sedelectronica.es | espublico gestiona (Wicket) | Tablón (~1 anuncio vigente), catálogo de trámites urbanísticos |
| Junta CYL PlanPublica | https://servicios.jcyl.es/PlanPublica/ | Java | NUM aprobada (PU/NUM 2014) — `provincia=49&municipio=119` |
| IDECyL GeoServer | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS 2.0 | 4 sectores (`ED-1`, `ED-2`, `ED-3`, `PP-1`), `c_mun=49119` |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `urbanismo:plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
- **Filtro:** `CQL_FILTER n_mun='Molacillos'`
- **Sectores:** ED-1, ED-2, ED-3 (estudio de detalle) y PP-1 (plan parcial), polígonos en WGS84

### 2. Junta CYL — documentación aprobada

- Archivo PLAU: `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=119`
- Documento principal: **Normas Urbanísticas Municipales** (PU/NUM, aprobación 2014)
- Información pública (PLAI): sin filas al 2026-09-24

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://molacillos.sedelectronica.es/board/
- Tabla espublico con enlace `preview-document/` (anuncios administrativos; poco urbanismo reciente)

### 4. Sede — catálogo de trámites

- **URL:** https://molacillos.sedelectronica.es/dossier.0
- Trámites informativos: licencias urbanísticas, declaración responsable, modificaciones de planeamiento, etc. (sin histórico de expedientes resueltos)

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales si mencionan licencia/obra (ventana corta)
2. **Catálogo `/dossier.0`** — páginas de trámite (sin listado de concesiones)
3. No hay dataset abierto de licencias con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 4 polígonos (ED-1, ED-2, ED-3, PP-1)
  - Capas `plau_cyl_planes_parciales` / `plau_cyl_instrumentos_ambito` consultables por municipio
- **Estrategia:** ingestión WFS por `n_mun='Molacillos'`; filas del tablón enriquecidas por coincidencia de título; licencias sin GIS → centroide municipal + jitter
- **Limitaciones:** sin visor urbanístico municipal; sede no expone geometría por expediente; tablón sin anuncios urbanísticos recientes

## Limitaciones

- Municipio pequeño: pocos anuncios en tablón
- `/info.0` en sede devuelve bucle de redirecciones (no usado)
- Licencias: solo trámites informativos, no concesiones históricas publicadas
- Web municipal inactiva

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` y centroide
2. Semillas PlanPublica JCYL (PLAU/PLAI) → proyectos de planeamiento
3. Tablón espublico → proyectos/licencias filtrados por keywords
4. Páginas informativas sede (board + dossier) → licencias de referencia

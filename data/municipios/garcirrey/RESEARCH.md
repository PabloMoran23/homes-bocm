# Garcirrey — investigación portal ayuntamiento

**Fecha:** 2026-09-17  
**Slug:** `garcirrey`  
**BOCyL regional (referencia):** 1 fila

## Resumen

Garcirrey (Salamanca, Castilla y León) **no dispone de web corporativa** activa (`garcirrey.es`, `aytogarcirrey.es` sin respuesta). La publicación urbanística se concentra en:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://garcirrey.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (vacío), catálogo de trámites (`/dossier`) |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | Instrumento SPG (Sin Planeamiento General), c_mun=37149 |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoServer WFS 2.0 | 1 polígono municipal (ámbito SPG) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumento de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas consultadas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0), `plau_cyl_sectores` (0)
- **Filtro:** `n_mun = 'Garcirrey'`, `c_mun = 37149`
- **Instrumento:** «Sin Planeamiento General» (SPG), título «SIN PLANEAMIENTO GENERAL»
- **Documentación:** https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=278452

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://garcirrey.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- **Estado:** tablón vacío (0 filas con `preview-document` a septiembre 2026)

### 3. Sede electrónica — catálogo de trámites

- **URL:** https://garcirrey.sedelectronica.es/dossier
- **Formato:** listado HTML con enlaces `/catalog/t/{uuid}`
- Trámites urbanísticos detectados: Declaración Responsable/Comunicación, Licencia o Autorización Urbanística, Modificación/Renuncia de Licencia, Certificado/Informe Urbanístico, Actuación Urbanística, Recepción de Obras de Urbanización

### 4. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=37&municipio=149`
- Información pública: `searchVPubDocMuniPlai.do?provincia=37&municipio=149`
- Documento SPG: `openDocuIndice.do?cDocId=278452`

## Fuentes de licencias

1. **Tablón sede** — vacío; sin anuncios de licencias publicados
2. **Catálogo trámites** (`/dossier`) — páginas informativas de solicitud de licencia (sin histórico de concesiones)
3. **Páginas informativas** — tablón y dossier como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 MultiPolygon (ámbito municipal SPG, ~84 km²)
  - Sin sectores ni planes parciales en WFS
  - Sin visor urbanístico municipal propio
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Garcirrey'`); enriquecimiento por coincidencia de título en tablón (si hubiera filas); resto centroide municipal + jitter
- **Limitaciones:** solo polígono de ámbito municipal (no por expediente); tablón vacío; licencias sin GIS enlazable; consulta de expedientes en sede requiere identificación

## Limitaciones

- Sin web corporativa municipal
- Tablón sede vacío
- Municipio sin PGOU/NUM aprobado (SPG)
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS IDECyL → proyecto SPG con `geom_geojson` (polígono municipal)
2. Semillas Junta CYL (PLAI/PLAU + openDocuIndice) → proyecto de planeamiento
3. Catálogo sede (`/dossier`) → trámites urbanísticos informativos (licencias y proyectos)
4. Tablón espublico → monitorizado (vacío actualmente)

# Castillejo de Martín Viejo — investigación portal ayuntamiento

**Fecha:** 2026-09-12  
**Slug:** `castillejo-de-martin-viejo`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Castillejo de Martín Viejo (Salamanca, CYL) es un municipio rural pequeño (~200 hab.) que publica trámites y anuncios en **sede espublico gestiona** y el planeamiento histórico en **PlanPublica / IDECyL** de la Junta de Castilla y León. No dispone de web corporativa activa ni visor urbanístico municipal propio.

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://castillejodemartinviejo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites urbanísticos |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta CYL | Archivo planeamiento (DSU 1976) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoServer | Delimitación suelo urbano (polígono municipal) |
| Web corporativa | http://www.aytocastillejodemartinviejo.es | — | **Inactiva** (404 / DNS no resuelve) |

**Códigos administrativos:** INE `37096`, PlanPublica provincia `37` / municipio `096`, DIR3 `L01370969`.

## Fuentes de proyectos / expedientes

### 1. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=096`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=096`
- **Contenido vigente:** 1 documento — **DSU SIN ORDENANZAS** (Delimitación de Suelo Urbano, aprobación 15/11/1976)
- **Enlace PDF:** `openDocumento.do?cDocId=278387` (vía `url_doc_info` en WFS)

### 2. IDECyL WFS — instrumentos y sectores

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `CQL_FILTER=c_mun='37096'`
- **Capas consultadas:**
  - `urbanismo:plau_cyl_instrumentos_ambito` → **1 feature** (DSU, MultiPolygon ~155 km²)
  - `urbanismo:plau_cyl_sectores` → 0 features
  - `urbanismo:plau_cyl_planes_parciales` → 0 features
- **Campos útiles:** `n_titulo`, `n_instrum`, `c_plan`, `f_aprob`, `url_doc_info`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://castillejodemartinviejo.sedelectronica.es/board
- **Formato:** tabla HTML espublico (DataTables)
- **Estado:** vacío («No se han encontrado elementos») a fecha de investigación
- **Nota:** `/info` provoca bucle de redirección; usar `/info.0` con cookie jar

### 4. Sede electrónica — catálogo de trámites

- **URL:** https://castillejodemartinviejo.sedelectronica.es/dossier.0
- **Formato:** enlaces `/catalog/t/{uuid}` (112 trámites totales)
- **Urbanismo relevante:** Solicitud de Licencia o Autorización Urbanística, Declaración Responsable en Materia Urbanística, Modificación del Planeamiento, Solicitud de Actuación Urbanística, etc.
- **Limitación:** páginas informativas de trámite, no listado de expedientes resueltos

## Fuentes de licencias

1. **Catálogo sede** — trámites informativos de licencias urbanísticas, actividades, ocupación, etc.
2. **Tablón sede** — vacío; se mantiene como fuente incremental cuando publiquen concesiones
3. No hay dataset histórico de licencias concedidas con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` con `c_mun='37096'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - 1 polígono MultiPolygon (delimitación DSU del término municipal, no expedientes puntuales)
- **Estrategia:** ingestión directa desde WFS en adapter; enriquecimiento por código de sector si aparecen en tablón futuro
- **Limitaciones:**
  - Sin visor SIG municipal ni sectores/PP desglosados en WFS
  - Tablón vacío: expedientes recientes (p. ej. granja porcina BOCYL 2026) no indexables vía scrape
  - Licencias sin georreferencia en fuentes públicas
  - Web corporativa inactiva

## Limitaciones

- Tablón e información pública sede sin anuncios indexables
- Web `aytocastillejodemartinviejo.es` / `castillejodemartinviejo.es` no resuelve o devuelve 404
- Certificado SSL sede con cadena incompleta → `insecure_ssl: true`
- Municipio con planeamiento mínimo (solo DSU 1976 sin ordenanzas)

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + PlanPublica PLAU/PLAI + tablón sede + catálogo trámites + páginas semilla JCyL
2. **licencias.jsonl:** catálogo trámites sede (páginas informativas) + tablón cuando publique concesiones

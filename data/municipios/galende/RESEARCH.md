# Galende — investigación portal ayuntamiento

**Fecha:** 2026-08-19  
**Slug:** `galende`  
**BOCYL regional (referencia):** 3 filas

## Resumen

Galende (Zamora, Sanabria) publica planeamiento y trámites urbanísticos en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytogalende.net/ | Joomla 4 + Helix Ultimate + jDownloads | Tablón de anuncios → categoría Urbanismo (PDFs/ZIPs) |
| Sede electrónica | https://galende.sedelectronica.es/ | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta de Castilla y León | Archivo planeamiento aprobado + información pública |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoServer | Sectores y normas urbanísticas municipales |

## Fuentes de proyectos / expedientes

### 1. Web corporativa — jDownloads Urbanismo

- **URL:** https://www.aytogalende.net/index.php/tablon-de-anuncios/category/3-urbanismo
- **Formato:** jDownloads con listado HTML (`<b><a href="/index.php/tablon-de-anuncios/download/3-urbanismo/...">`)
- **Paginación:** 8 ítems por página (`?start=8`, `?start=16`…)
- **Contenido (~15 documentos):** estudios de detalle (expdte 235/2026), modificaciones normas urbanísticas, AUSR (autorizaciones uso suelo rústico), exposiciones públicas por parcela/polígono, proyectos de sendas
- **Ejemplos:** aprobación inicial estudio de detalle parcelas 246-247 San Martín de Castañeda; AUSR POL 13 parcelas 694-695 Cubelo

### 2. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=85`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=49&municipio=85`
- **INE:** c_mun `49085` (provincia 49, municipio 85)
- **Enlaces:** `openDocumento.do?cDocId=...`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://galende.sedelectronica.es/board
- **Formato:** enlaces `preview-document/{uuid}` (sin tabla estructurada en la portada)
- **Contenido actual:** mayormente anuncios administrativos (electores, IAE, bandos); sin urbanismo indexado en primera página
- **Dossier:** `/dossier.0` — catálogo de trámites (timeout frecuente >15s)

### 4. IDECyL WFS — sectores y normas

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `c_mun='49085'`
- **Capas:** `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_sectores` (19), `plau_cyl_planes_parciales` (0)
- **Sectores ejemplo:** ED.vig.2 (suelo urbano no consolidado, residencial)

## Fuentes de licencias

1. **Catálogo sede** — trámites informativos de licencia urbanística (cuando dossier responde)
2. **Tablón sede** — sin concesiones de licencia publicadas en investigación
3. No hay listado histórico público de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `CQL_FILTER=c_mun='49085'`, `srsName=EPSG:4326`
  - 20 polígonos (1 instrumento NUM + 19 sectores ED.vig.*)
- **Estrategia:** ingestión directa desde WFS en adapter; enriquecimiento por código de sector (ED.vig.*) en filas jDownloads/PlanPublica cuando el título lo menciona
- **Limitaciones:**
  - Sin visor urbanístico propio en la web del ayuntamiento
  - Estudios de detalle y AUSR recientes solo en PDF sin enlace GIS
  - Licencias sin georreferencia en fuentes públicas
  - Dossier sede con timeouts intermitentes

## Limitaciones

- Tablón sede sin anuncios urbanísticos en portada (solo administrativos)
- Dossier `/dossier.0` puede tardar >15s o no responder
- jDownloads sin fechas estructuradas en listado (se infiere año del expediente)
- Municipio con 11 núcleos; documentos referencian localidades (San Martín de Castañeda, El Puente de Sanabria, Vigo de Sanabria, Cubelo…)

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + jDownloads urbanismo + PlanPublica PLAU/PLAI + tablón sede + catálogo trámites + páginas semilla JCyL
2. **licencias.jsonl:** catálogo trámites sede (páginas informativas) + tablón cuando publique concesiones

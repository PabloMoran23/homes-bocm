# Saldaña — investigación portal ayuntamiento

**Municipio:** Saldaña (Palencia, Castilla y León)  
**INE:** 34157  
**PLAU:** provincia=34, municipio=157  
**Fecha:** 2026-09-01  
**BOCYL regional (referencia):** 2 avisos

## Resumen

Saldaña publica urbanismo y licencias en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://saldana.es | WordPress CMSMasters Dream City (`project` CPT) | NUM, plan parcial polígono industrial, documentación oficial |
| Sede electrónica | https://saldana.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites |
| Junta CYL / IDECyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | Sectores SU-NC 01–05, SUR 01–06, ámbito NUM |

## Fuentes identificadas

### 1. WordPress — CPT `project`

- **Urbanismo:** https://saldana.es/project/urbanismo/
- **Documentación oficial:** https://saldana.es/project/documentacion-oficial/
- **Formato:** páginas estáticas con enlaces directos a PDFs en `wp-content/uploads/`
- **REST API:** `/wp-json/wp/v2/project` (habilitada, 20+ páginas)
- **Contenido:** NUM aprobada 2016, plan parcial polígono industrial, derivados (DI-EA, DI-EH, DN-CT, etc.)

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://saldana.sedelectronica.es/board
- **Formato:** tabla HTML espublico (6 columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- **Extracto inicio:** https://saldana.sedelectronica.es/info.0 (sin anuncios urbanismo en ventana actual)
- **SSL:** certificado con cadena incompleta en CI → `insecure_ssl: true`
- **Sin RSS** en `/board.rss`

### 3. Sede electrónica — catálogo trámites

- **URL:** https://saldana.sedelectronica.es/dossier.0
- **Formato:** enlaces `/catalog/t/{uuid}` (respuesta lenta ~60–90 s)
- Sección Urbanismo y Vivienda en menú sede

### 4. Junta CYL — PlanPublica

- **Archivo aprobado:** `searchVPubDocMuniPlau.do?provincia=34&municipio=157` — 11 documentos (`doGoBoletin`)
- **Info pública:** `searchVPubDocMuniPlai.do?provincia=34&municipio=157`
- **PDF directo:** `http://www.jcyl.es/plaupdf//34/34157/{cDocId}/{filename}.pdf`
- **NUM vigente:** `34157-PU-20161018-293338` (cDocId=293338)

### 5. IDECyL WFS

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (11), `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0)
- **Filtro:** `n_mun='Saldaña'` o `c_mun='34157'`
- **Sectores:** SU-NC 01–05, SUR 01–06

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- **Documentación oficial:** modelos PDF de licencia urbanística, vado, DR obras
- **Tablón:** anuncios puntuales (mayoría recaudación/padrón en ventana actual)
- Sin listado histórico de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 11 polígonos sectoriales
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`, `c_mun`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código sector (SU-NC, SUR) en título; PDFs/tablón sin GIS usan centroide municipal + jitter
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio
  - Plan parcial polígono industrial solo en PDF (no en capa `planes_parciales`)
  - Licencias sin geolocalización en fuentes públicas
  - Sede dossier muy lento; catálogo puede quedar vacío en CI

## Limitaciones

- WordPress usa dominio alternativo `saldana.maximacomunicacion.es` en canonical; scraping en `saldana.es`
- Tablón sede: ventana corta (~5 anuncios), sin API
- `/dossier` sin sufijo `.0` redirige; usar `.0` obligatorio
- Licencias sin geolocalización en fuentes públicas

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (12 features)
2. PLAU/PLAI JCyL → proyectos PDF (`doGoBoletin` parse)
3. WordPress PDFs urbanismo + REST `project` → proyectos
4. Tablón espublico `/board` → proyectos/licencias filtrados
5. Semillas PlanPublica + páginas web → proyectos de planeamiento
6. IDs estables: `saldana-{lic|proy}-{sha256[:14]}`

## Referencia adapters

- espublico tablón + dossier: `duenas.py` (mismo patrón Palencia/CYL)
- IDECyL WFS geometría: `villadangos_del_paramo.py`, `aguilar_de_campoo.py`

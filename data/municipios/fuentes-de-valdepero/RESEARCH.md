# Fuentes de Valdepero — investigación portal ayuntamiento

**Municipio:** Fuentes de Valdepero (Palencia, Castilla y León)  
**Fecha:** 2026-09-16  
**BOCYL regional (referencia):** 1 aviso

## Resumen

Fuentes de Valdepero publica urbanismo y licencias en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://fuentesdevaldepero.es | WordPress | Sección urbanismo (sin PDFs listados) |
| Sede electrónica | https://fuentesdevaldepero.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (111) |
| Junta CYL / SIUCyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | NUM, 5 planes parciales, 10 sectores |

## Fuentes identificadas

### 1. WordPress — urbanismo

- **URL semilla:** https://fuentesdevaldepero.es/ayuntamiento/urbanismo/
- **Formato:** página estática sin listado de expedientes ni PDFs enlazados
- **REST API:** disponible (`/wp-json/`) pero sin entradas urbanismo scrapeables

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://fuentesdevaldepero.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- **Contenido actual:** anuncio expropiación EDAR (expediente 6/2026, urbanismo/infraestructura)
- **SSL:** certificado con cadena incompleta en CI → `insecure_ssl: true`

### 3. Sede electrónica — catálogo trámites

- **URL:** https://fuentesdevaldepero.sedelectronica.es/dossier.0 (requiere opener con cookie jar limpio; `/dossier/.0` puede bucle)
- **Formato:** enlaces `/catalog/t/{uuid}` con título del trámite
- Trámites urbanismo/licencias: Solicitud de Licencia o Autorización Urbanística, Declaración Responsable, Modificación Planeamiento, etc.

### 4. Junta CYL — PlanPublica

- **Info pública:** `searchVPubDocMuniPlai.do?provincia=34&municipio=086` — NUT en información pública (2025)
- **Archivo aprobado:** `searchVPubDocMuniPlau.do?provincia=34&municipio=086`
- Documentos: DSU original (1979), modificaciones DSU (2016, 2024), DOAS subregional
- Código municipio 086 = INE 34086 (Fuentes de Valdepero, Palencia)

### 5. IDECyL WFS (SIUCyL)

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:**
  - `urbanismo:plau_cyl_instrumentos_ambito` — 1 NUM (MultiPolygon)
  - `urbanismo:plau_cyl_planes_parciales` — 5 planes parciales
  - `urbanismo:plau_cyl_sectores` — 10 sectores
- **Filtro:** `n_mun ILIKE '%VALDEPERO%'`

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- **Catálogo sede:** páginas informativas de trámites (licencia urbanística, actividad, ocupación, etc.)
- **Tablón:** anuncios puntuales cuando mencionan licencias/obras
- Sin listado histórico de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM
  - SIUCyL WFS `urbanismo:plau_cyl_planes_parciales` — 5 polígonos
  - SIUCyL WFS `urbanismo:plau_cyl_sectores` — 10 polígonos
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`, `url_doc_info`
- **Estrategia:** descarga WFS por municipio (`n_mun='Fuentes de Valdepero'`); enriquecimiento por código de sector en título PLAU/tablón; expedientes sin GIS usan centroide municipal + jitter
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio
  - Licencias y anuncios puntuales del tablón sin polígono enlazable
  - WordPress urbanismo sin contenido scrapeable

## Limitaciones

- Tablón sede: ventana corta (~1 anuncio), sin API
- Dossier requiere opener dedicado (redirects espublico)
- Sin dataset abierto de licencias concedidas

## Adapter

- **Módulo:** `municipio/adapters/fuentes_de_valdepero.py`
- **Clase:** `FuentesDeValdeperoAyuntamientoAdapter`
- **Fuentes scrapeadas:** WFS IDECyL + PLAU/PLAI + tablón sede + catálogo trámites

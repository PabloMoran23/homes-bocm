# Paredes de Nava — investigación portal ayuntamiento

**Municipio:** Paredes de Nava (Palencia, Castilla y León)  
**Fecha:** 2026-09-28  
**BOCYL regional (referencia):** 1 aviso (`bocyl`)

## Resumen

Paredes de Nava publica urbanismo y trámites en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://paredesdenava.es | WordPress Divi (Diputación Palencia) | Urbanismo, noticias `ic_urbanismo`, documentación planeamiento |
| Sede electrónica | https://paredesdenava.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites |
| Junta CYL / IDECyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | Instrumentos, plan parcial, sectores |

## Fuentes identificadas

### 1. WordPress — categoría Urbanismo

- **URL semilla:** https://paredesdenava.es/urbanismo/ (2 páginas de entradas `ic_urbanismo`)
- **Formato:** listado `<article>` con título y enlace
- **Contenido:** modificaciones normas subsidiarias, plan parcial polígono industrial, estudios de detalle, parque eólico Encillas, adecuación camino del ferrocarril

### 2. WordPress — sección Ayuntamiento → Urbanismo

- **URL:** https://paredesdenava.es/ayuntamiento/urbanismo/
- **Subsecciones** (`g=10&st=0..2`): documentación informativa, planeamiento municipales, licencias
- Enlaces a fichas `/urbanismo/{slug}/` con títulos en `<h4>`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://paredesdenava.sedelectronica.es/board/
- **Formato:** tabla espublico con `preview-document/{uuid}`
- Ventana corta; mayoría avisos no urbanísticos (arrendamientos polígono, etc.)

### 4. Sede electrónica — catálogo trámites

- **URL:** https://paredesdenava.sedelectronica.es/dossier.0
- Enlaces `/catalog/t/{uuid}` (carga lenta; opcional en adapter)

### 5. Junta CYL — PlanPublica

- **Código municipio PlanPublica:** provincia `34`, municipio `123` (INE 34123)
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=123`
- **Archivo aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=123`
- **Índice PLAU:** `lplanes.plau?municipio=3412300001701`
- Instrumento principal: **Normas Subsidiarias de Planeamiento Municipal** (aprobación 1997, BOCyL 1997-07-29)

## Licencias

No hay dataset abierto de concesiones históricas con coordenadas.

- Sección web «Licencias y otros actos de intervención en el uso del suelo» (`g=20`) sin listado descargable público
- **Catálogo sede:** trámites informativos de licencia/obra (cuando responde `dossier.0`)
- **Tablón:** anuncios puntuales si mencionan licencias/obras

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono (`n_mun='Paredes de Nava'`)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 1 sector
  - URL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_instrum`, `c_plan`, `n_sector`, `f_bocyl`, `url_doc_info`
- **Estrategia:** ingestión WFS por municipio; noticias/tablón sin GIS usan centroide municipal + jitter
- **Limitaciones:**
  - Sin visor ArcGIS municipal propio
  - Expedientes sede y licencias sin polígono enlazable
  - Documentación urbanística mayormente PDF en WordPress/PlanPublica

## Limitaciones

- WordPress REST API no usada; solo HTML
- Tablón sede: ventana corta
- `dossier.0` puede tardar >60s; adapter tolera fallo
- Certificado sede: `insecure_ssl: true` en entornos CI

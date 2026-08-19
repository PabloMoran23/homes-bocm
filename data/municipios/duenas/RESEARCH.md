# Dueñas — investigación portal ayuntamiento

**Municipio:** Dueñas (Palencia, Castilla y León)  
**Fecha:** 2026-08-16  
**BOCYL regional (referencia):** 3 avisos

## Resumen

Dueñas publica urbanismo y licencias en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://duenas.es | WordPress (Diputación Palencia) | Noticias urbanismo, PGOU, estudios de detalle, convenios |
| Sede electrónica | https://duenas.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia |
| Junta CYL / SIUCyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | Sectores, planes parciales, ámbito PGOU |

## Fuentes identificadas

### 1. WordPress — categoría Urbanismo

- **URL semilla:** https://duenas.es/urbanismo/ (4 páginas, 17 entradas)
- **Formato:** listado `<article>` con título, fecha (`datetime`) y enlace a noticia
- **Contenido:** modificaciones PGOU, plan especial casco histórico, estudios de detalle, convenios urbanísticos (Camponecha, Gestamp, Siro), proyectos NUF-6, etc.
- **Descargas:** enlaces `download/{id}` con PDFs en fichas individuales
- **REST API:** deshabilitada (`401 No REST API`)

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://duenas.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- **Extracto inicio:** https://duenas.sedelectronica.es/info.0
- Ventana corta (~10 anuncios); mayoría no urbanismo (bandos, censos, subvenciones)
- **SSL:** certificado con cadena incompleta en CI → `insecure_ssl: true`

### 3. Sede electrónica — catálogo trámites

- **URL:** https://duenas.sedelectronica.es/dossier.0 (`.0` obligatorio; `/dossier` redirige en bucle)
- **Formato:** enlaces `/catalog/t/{uuid}` con título del trámite
- Trámites urbanismo/licencias: Solicitud de Licencia o Autorización Urbanística, Declaración Responsable, Modificación Planeamiento, etc. (20+ trámites)

### 4. Junta CYL — PlanPublica

- **Info pública:** `searchVPubDocMuniPlai.do?provincia=34&municipio=117`
- **Archivo aprobado:** `searchVPubDocMuniPlau.do?provincia=34&municipio=117`
- Código municipio 117 = INE 34117 (Dueñas, Palencia)

### 5. Portal transparencia sede

- **URL:** https://duenas.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (65 documentos)
- Carga vía AJAX Wicket (`exp` links); no scrapeado (tablón + WP + WFS cubren expedientes)

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones históricas.

- **Catálogo sede:** páginas informativas de trámites (licencia urbanística, actividad, ocupación, etc.)
- **Tablón:** anuncios puntuales cuando mencionan licencias/obras (p. ej. cartel obra PREE-500)
- Sin listado histórico de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCyL WFS `urbanismo:plau_cyl_sectores` — 21 polígonos (`n_mun='Dueñas'`)
  - SIUCyL WFS `urbanismo:plau_cyl_planes_parciales` — 4 planes parciales
  - SIUCyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 ámbito PGOU
  - URL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `f_bocyl`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título (S-14, S-15, U-5, NUF-6, Sector N); expedientes WordPress/tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:**
  - VisualUrb-maps (comercial) no accesible para scraping
  - No hay visor municipal ArcGIS propio
  - Licencias y expedientes puntuales sin polígono enlazable
  - Consulta expedientes sede requiere certificado digital

## Limitaciones

- WordPress REST API deshabilitada; solo HTML
- Tablón sede: ventana corta, sin API
- `/dossier` sin sufijo `.0` → bucle de redirección
- Licencias sin geolocalización en fuentes públicas
- PlanPublica: tabla de documentos con sesión JS; usado como semilla URL

## Estrategia adapter

1. WFS SIUCyL → proyectos con `geom_geojson` (26 features)
2. WordPress `/urbanismo/` paginado → proyectos con enriquecimiento sector
3. Tablón espublico `/board` + `/info.0` → proyectos/licencias filtrados
4. Catálogo trámites `/dossier.0` → licencias y proyectos informativos
5. Semillas PlanPublica + PGOU → proyectos de planeamiento
6. IDs estables: `duenas-{lic|proy}-{sha256[:14]}`

## Referencia adapters

- espublico tablón + dossier: `pelabravo.py`
- IDECyL WFS geometría: `villadangos_del_paramo.py`

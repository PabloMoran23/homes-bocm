# Morales del Vino — investigación portal ayuntamiento

**Fecha:** 2026-09-25  
**Slug:** `morales-del-vino`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Morales del Vino (Tierra del Vino, Zamora) publica urbanismo en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.moralesdelvino.es | WordPress | Ordenanzas municipales (tasa licencias urbanísticas), instancias (declaración responsable de obras) |
| Sede electrónica | https://aytomoralesdelvino.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites (`/dossier`), transparencia |
| Junta CYL / PlanPublica | https://servicios.jcyl.es/PlanPublica/ | Java | Archivo planeamiento aprobado e información pública (`provincia=49&municipio=138`) |
| IDECyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoServer WFS | Sectores, planes parciales e instrumentos (`c_mun=49138`) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (10), `plau_cyl_sectores` (24)
- **Filtro:** `n_mun = 'Morales del Vino'`, código municipal `49138`
- Polígonos en WGS84 con metadatos de sector/plan y enlaces documentales cuando existen

### 2. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=138`
- Información pública: `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=49&municipio=138`
- Tabla HTML con `openDocuIndice.do?cDocId=…` / `openDocumento.do?cDocId=…`

### 3. Sede electrónica — tablón y trámites

- **Tablón:** https://aytomoralesdelvino.sedelectronica.es/board/ (tabla espublico; puede estar vacío en ventana actual)
- **Catálogo:** https://aytomoralesdelvino.sedelectronica.es/dossier — trámites URBANISMO Y VIVIENDA, licencias
- **Info sede:** https://aytomoralesdelvino.sedelectronica.es/info — enlaces a licencia urbanística y obra menor (DR)

### 4. Web municipal

- https://www.moralesdelvino.es/instancias-de-solicitudes/ — formularios (DR obras, autoliquidación II.TT.)
- Ordenanzas en web y sede transparencia (tasa licencias, informes urbanísticos)

## Fuentes de licencias

1. **Tablón sede** — anuncios si mencionan licencias/obra (ventana corta)
2. **Catálogo sede** (`/dossier`) — trámites de licencia urbanística y obra menor (DR)
3. **Web** — página de instancias (informativa, sin histórico de concesiones)

No hay registro histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 24 polígonos de sectores
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 10 ámbitos
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — instrumento de planeamiento (NUM/PGOU)
- **Estrategia:** descarga WFS por `n_mun='Morales del Vino'`; proyectos del tablón/PLAU enriquecidos por coincidencia de título; licencias sin GIS
- **Limitaciones:** sin visor urbanístico municipal propio; tablón puede estar vacío; licencias solo como trámites informativos

## Limitaciones

- Tablón espublico sin API y con ventana temporal limitada
- Licencias sin geolocalización en fuentes públicas
- Sede requiere cookies de sesión para algunas rutas (`/info`, `/dossier`)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. PlanPublica PLAU/PLAI → proyectos documentales
3. Tablón espublico → proyectos/licencias filtrados por keywords
4. Catálogo sede + páginas informativas → licencias (trámites)

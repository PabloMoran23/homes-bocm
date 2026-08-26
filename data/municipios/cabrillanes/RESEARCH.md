# Cabrillanes — investigación portal ayuntamiento

**Fecha:** 2026-08-26  
**Slug:** `cabrillanes`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Cabrillanes publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytocabrillanes.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística (enlaces Junta CYL), trámites |
| Sede electrónica | https://aytocabrillanes.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (`/info`), transparencia (330 docs urbanismo) |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 022) |

`cabrillanes.sedelectronica.es` responde como sede indeterminada (sin contenido).

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y ámbito

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (6: SUED-1/2/4, SNC-1/2/3), `plau_cyl_instrumentos_ambito` (1 PGOU), `plau_cyl_planes_parciales` (0)
- **Filtro:** `n_mun = 'Cabrillanes'`
- GeoJSON WGS84 con polígonos de sectores

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://aytocabrillanes.sedelectronica.es/info (redirect desde `/board`)
- **Formato:** enlaces `preview-document` espublico (Wicket AJAX)
- Ventana corta (~10 anuncios); mayoría administrativa (contratación, subvenciones)
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

### 3. Web OpenCms — normativa y Junta CYL

- **Normativa:** https://www.aytocabrillanes.es/ayuntamiento/urbanismo/
- Enlaces a planeamiento CYL:
  - Info pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=022`
  - Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=022` (2 instrumentos: PGOU y NUM)

### 4. Transparencia sede — urbanismo

- **URL:** https://aytocabrillanes.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (330 documentos)
- Navegación AJAX Wicket; el adapter usa tablón + WFS + semillas web

### 5. Catálogo trámites sede (`/dossier`)

- Puede timeout en CI; el adapter lo intenta para licencias/trámites urbanismo

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales cuando mencionan licencias
2. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)
3. **Web** — sin páginas dedicadas de licencia urbanística detectadas (solo enlace genérico a trámites)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`: SUED-*, SNC-*)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — ámbito PGOU
- **Estrategia:** descarga WFS por municipio (`n_mun='Cabrillanes'`); enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales sin polígono enlazable; sin visor urbanístico municipal propio; transparencia requiere AJAX Wicket

## Limitaciones

- Tablón sede: ventana corta, sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio (solo WFS regional IDECyL)
- Web corporativa sin PDFs locales de planeamiento (solo enlaces Junta CYL)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (7 sectores/ámbito)
2. Tablón espublico → proyectos/licencias filtrados
3. Semillas normativa + JCyl → proyectos de planeamiento
4. Catálogo sede → trámites licencia/urbanismo cuando responde

# La Robla — investigación portal ayuntamiento

**Fecha:** 2026-08-13  
**Slug:** `la-robla`  
**BOCYL regional (referencia):** 4 filas

## Resumen

La Robla publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytolarobla.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística, modificación puntual El Crispín (PDFs), trámites/licencias |
| Sede electrónica | https://aytolarobla.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia (153 docs urbanismo) |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 142) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (16), `plau_cyl_planes_parciales` (3), `plau_cyl_instrumentos_ambito` (1)
- **Filtro:** `n_mun = 'La Robla'`
- GeoJSON WGS84 con polígonos de sectores y planes parciales

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://aytolarobla.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~10 anuncios); incluye categoría **Urbanismo** cuando hay expedientes activos (p. ej. censo amianto 933/2025)
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

### 3. Web OpenCms — normativa y Junta CYL

- **Normativa:** https://www.aytolarobla.es/ayuntamiento/normativa-municipal/urbanismo/
- **Modificación puntual nº6 El Crispín:** PDFs (memoria, planos, anexos) y ZIP de aprobación inicial 2021
- Enlaces a planeamiento CYL:
  - Info pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=142`
  - Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=142`

### 4. Transparencia sede — urbanismo

- **URL:** https://aytolarobla.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (153 documentos)
- Navegación AJAX Wicket; el adapter usa tablón + WFS + semillas web

### 5. Catálogo trámites sede (`/dossier`)

- Trámites urbanismo/licencias cuando responde (puede timeout en CI)

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura
2. **Tablón sede** — anuncios puntuales cuando mencionan licencias
3. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`, `c_id_sect`)
  - IDECyL WFS `plau_cyl_planes_parciales` e `plau_cyl_instrumentos_ambito`
- **Estrategia:** descarga WFS por municipio (`n_mun='La Robla'`); enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales sin polígono enlazable; sin visor urbanístico municipal propio; consulta expedientes sede requiere login; modificación puntual publicada solo como PDFs

## Limitaciones

- Tablón sede: ventana corta, sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio (solo WFS regional IDECyL)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados
3. Páginas trámite OpenCms → licencias informativas
4. Semillas normativa + modificación puntual + JCyl → proyectos de planeamiento

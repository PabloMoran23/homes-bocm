# Villadangos del Páramo — investigación portal ayuntamiento

**Fecha:** 2026-08-05  
**Slug:** `villadangos-del-paramo`  
**BOCYL regional (referencia):** 9 filas

## Resumen

Villadangos del Páramo publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytovilladangosdelparamo.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística, trámites/licencias (HTML), tablón (redirige a sede) |
| Sede electrónica | https://villadangosdelparamo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia |
| Junta CYL | http://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 205) |

## Fuentes de proyectos / expedientes

### 1. SIUCyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (11), `plau_cyl_planes_parciales` (4), `plau_cyl_instrumentos_ambito` (1)
- **Filtro:** `n_mun = 'Villadangos del Páramo'`, `c_mun = 24205`
- GeoJSON WGS84 con polígonos de sectores S.U.N.C. (ej. `S.U.N.C.- V1`)

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://villadangosdelparamo.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~10 anuncios); incluye categoría **Urbanismo** (ruina, desafectación, etc.)
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

### 3. Web OpenCms — normativa y Junta CYL

- **Normativa:** https://www.aytovilladangosdelparamo.es/ayuntamiento/normativa-municipal/urbanismo/
- Enlaces a planeamiento CYL:
  - Info pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=205`
  - Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=205`

### 4. Catálogo trámites sede (`/dossier`)

- Trámites urbanismo/licencias cuando responde (timeout frecuente en CI)

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental
2. **Tablón sede** — anuncios puntuales cuando mencionan licencias
3. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`, `c_id_sect`)
  - SIUCyL WFS `plau_cyl_planes_parciales` e `plau_cyl_instrumentos_ambito`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales (ruina, desafectación) sin polígono enlazable; visor municipal inexistente; consulta expedientes sede requiere login

## Limitaciones

- Tablón sede: ventana corta, sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS SIUCyL → proyectos con `geom_geojson`
2. Tablón espublico → proyectos/licencias filtrados
3. Páginas trámite OpenCms → licencias informativas
4. Semillas normativa + JCyl → proyectos de planeamiento

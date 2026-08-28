# Hospital de Órbigo — investigación portal ayuntamiento

**Fecha:** 2026-08-28  
**Slug:** `hospital-de-orbigo`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Hospital de Órbigo publica urbanismo en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa OpenCms | https://www.aytohospitaldeorbigo.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística, enlaces a archivo PLAI JCYL |
| Web Joomla | https://www.hospitaldeorbigo.com | Joomla 4 / Helix Ultimate | Plan Urbanístico 2015, anuncios, PDF estudio de detalle SEMARK |
| Sede electrónica | https://hospitaldeorbigo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, trámites OBRAS (licencias), catálogo urbanismo |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Archivo planeamiento (provincia 24, municipio 107) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores e instrumentos

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (2: ED-1, ED-2), `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0)
- **Filtro:** `c_mun = '24107'` (INE)
- GeoJSON WGS84 con polígonos de estudios de detalle / sectores

### 2. PLAI JCYL — archivo planeamiento

- **URL:** `searchVPubDocMuniPlai.do?provincia=24&municipio=107`
- Documento vigente: **NORMAS URBANÍSTICAS MUNICIPALES** (NUM, aprobación 2013)

### 3. Joomla — plan y anuncios

- **Plan urbanístico:** https://www.hospitaldeorbigo.com/index.php/ayuntamiento/urbanismo/plan-urbanistico (PGOU 2015, enlace BOCYL)
- **Anuncios:** https://www.hospitaldeorbigo.com/index.php/ayuntamiento/urbanismo/anuncios
- **PDF:** `/images/ficheros/estudiodetallesemark.pdf` — Estudio de detalle SEMARK AC GROUP

### 4. Sede electrónica — tablón de anuncios

- **URL:** https://hospitaldeorbigo.sedelectronica.es/board
- Tabla HTML espublico; en la ventana actual (~3 anuncios) sin categoría Urbanismo (presupuesto, empleo público)
- **SSL:** `insecure_ssl: true` recomendado en algunos entornos

### 5. OpenCms — normativa

- **URL:** https://www.aytohospitaldeorbigo.es/ayuntamiento/normativa-municipal/urbanismo/
- Enlaces al archivo PLAI y planeamiento en información pública de Castilla y León

## Fuentes de licencias

1. **Sede — trámites OBRAS:** `citizen-service/d6fcc5b2-3497-419a-9add-f8e5a5e1ac1c` (declaración responsable obras menores, solicitud licencia obras mayores)
2. **Catálogo sede:** `/catalog/t/urbanismo` (si responde)
3. **Tablón sede** — sin licencias en ventana actual

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos ED-1 y ED-2 (`n_num_sect`)
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — ámbito municipal NUM
- **Estrategia:** descarga WFS por `c_mun='24107'`; enriquecimiento por código de sector en título (estudio de detalle); expedientes del tablón sin GIS usan centroide municipal + jitter
- **Limitaciones:** sin visor urbanístico municipal propio; licencias sin georef; consulta expedientes sede requiere Cl@ve; `/dossier` puede timeout en CI

## Limitaciones

- Tablón sede: ventana corta, sin API
- Página `/ayuntamiento/tramites-solicitudes/` muy lenta (>45s) — adapter usa sede OBRAS + normativa
- Licencias sin geolocalización en fuentes públicas
- Sin visor ArcGIS municipal (solo WFS regional IDECyL)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. PLAI JCYL → NUM y documentación aprobada
3. Joomla PDF/plan → estudio de detalle y PGOU
4. Tablón espublico → proyectos/licencias filtrados cuando aparecen
5. Páginas trámite sede/OpenCms → licencias informativas

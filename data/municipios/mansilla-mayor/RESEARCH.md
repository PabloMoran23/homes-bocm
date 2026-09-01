# Mansilla Mayor — investigación portal ayuntamiento

**Fecha:** 2026-08-30  
**Slug:** `mansilla-mayor`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Mansilla Mayor publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytomansillamayor.es | OpenCms (`es.samdipuleon.templates`, Diputación León) | Normativa urbanística, trámites, tablón (redirige a sede) |
| Sede electrónica | https://aytomansillamayor.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, transparencia (90 docs urbanismo) |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 095, INE 24095) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores e instrumentos

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (7), `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0)
- **Filtro:** `n_mun = 'Mansilla Mayor'`, `c_mun = 24095`
- GeoJSON WGS84 con polígonos de sectores SU-NC (ej. `ED-vmr-1`, `No asignado (ED-vmr-1)`)

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://aytomansillamayor.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~7 anuncios recientes); en la muestra actual predominan subvenciones y contratación, sin urbanismo explícito
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

### 3. Web OpenCms — normativa y Junta CYL

- **Normativa:** https://www.aytomansillamayor.es/ayuntamiento/normativa-municipal/urbanismo/
- Enlaces a planeamiento CYL:
  - Info pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=095`
  - Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=095`

### 4. Portal transparencia sede

- **URL:** https://aytomansillamayor.sedelectronica.es/transparency
- Sección **7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (90 documentos)
- Documentos PDF vía Wicket AJAX (sin API REST pública)

### 5. Catálogo trámites sede (`/dossier`)

- Trámites urbanismo/licencias cuando responde (timeout frecuente en CI)

## Fuentes de licencias

1. **Páginas informativas** — trámites/solicitudes, tablón, transparencia urbanismo
2. **Tablón sede** — anuncios puntuales cuando mencionan licencias (poca actividad urbanística en ventana actual)
3. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`, `c_id_sect`, ej. `24095ED-vmr-1`)
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — ámbito del instrumento normativo (NUM)
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales sin polígono enlazable; visor municipal inexistente; consulta expedientes sede requiere login; transparencia solo PDFs

## Limitaciones

- Tablón sede: ventana corta, sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (8 filas con geometría)
2. Tablón espublico → proyectos/licencias filtrados
3. Páginas informativas web/sede → licencias informativas
4. Semillas normativa + JCyL → proyectos de planeamiento

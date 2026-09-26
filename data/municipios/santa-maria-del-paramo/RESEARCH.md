# Santa María del Páramo — investigación portal ayuntamiento

**Fecha:** 2026-09-02  
**Slug:** `santa-maria-del-paramo`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Santa María del Páramo publica urbanismo en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.santamariadelparamo.es | Drupal 7 (bootstrap_business) | Área urbanismo, normas urbanísticas, formularios PDF, bandos |
| Sede electrónica | https://santamariadelparamo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites, consulta expedientes |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | PLAU/PLAI provincia 24, municipio 157 |
| Incidencias urbanas | https://stamariadelparamo-publicform.incidenciasurbanas.com | SaaS | Formulario ciudadano (sin listado histórico) |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores`, `plau_cyl_planes_parciales`, `plau_cyl_instrumentos_ambito`
- **Filtro:** `n_mun = 'Santa María del Páramo'`
- GeoJSON WGS84 con polígonos de sectores de planeamiento

### 2. PlanPublica JCyL (PLAU / PLAI)

- **Archivo aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=157`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=157`
- Tabla HTML con instrumentos (NUM, GU, PU, EU, CU…) y enlaces `openDocumento.do?cDocId=…`
- Ejemplos: normas urbanísticas (NUM), proyectos urbanización (GU), convenio urbanístico (CU 2025)

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://santamariadelparamo.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Incluye anuncios de **Licencias Urbanísticas** (p. ej. uso excepcional parcela 54 polígono 106, BOCYL 161/2026)
- **SSL:** puede requerir `insecure_ssl: true` en algunos entornos

### 4. Web Drupal — normativa y trámites

- **Urbanismo:** https://www.santamariadelparamo.es/areas-municipales?area=urbanismo
- **Documentación:** https://www.santamariadelparamo.es/areas-municipales/documentacion/urbanismo
- **Normas urbanísticas:** https://www.santamariadelparamo.es/es/normas-urbanisticas-municipales
- **Trámites:** https://www.santamariadelparamo.es/es/formularios/tramites-generales (licencias, declaraciones)

## Fuentes de licencias

1. **Páginas informativas web** — solicitud licencia urbanística, declaración responsable/comunicación
2. **Tablón sede** — anuncios de licencias urbanísticas cuando hay expedientes activos
3. **Catálogo sede** (`/dossier`) — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect`, `c_id_sect`)
  - IDECyL WFS `plau_cyl_planes_parciales` e `plau_cyl_instrumentos_ambito`
  - Enlace PLAU «ver planeamiento vigente en el mapa» (visor JCyL, no query directa por expediente)
- **Estrategia:** descarga WFS por municipio (`n_mun='Santa María del Páramo'`); enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales sin polígono enlazable; sin visor urbanístico municipal propio; consulta expedientes sede requiere login; incidenciasurbanas.com no expone geometría

## Limitaciones

- Tablón sede: ventana corta (~10 anuncios), sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio (solo WFS regional IDECyL)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. PLAU JCyL → instrumentos de planeamiento aprobados
3. Tablón espublico → proyectos/licencias filtrados
4. Páginas trámite Drupal + semillas normativa/JCyL → licencias informativas y proyectos de planeamiento

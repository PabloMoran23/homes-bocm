# Ayllón — investigación portal ayuntamiento

**Municipio:** Ayllón (Castilla y León, Segovia)  
**Fecha:** 2026-08-25

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Segovia9) | https://www.ayllon.es | Portal gestionado por Diputación de Segovia |
| Urbanismo | https://www.ayllon.es/urbanismo | Sección general de urbanismo |
| Urbanismo, Obras y Medio Ambiente | https://www.ayllon.es/urbanismo1 | Enlace a transparencia y documentación |
| Sede electrónica (espublico) | https://ayllon.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://ayllon.sedelectronica.es/board | ~6 anuncios (tributos, IBI, IAE; 1 urbanístico BOP) |
| Transparencia urbanismo | https://ayllon.sedelectronica.es/transparency/40aee2ea-0a61-4686-aa8b-a7a363c1b308/ | Urbanismo, obras públicas y medio ambiente |
| Catálogo trámites | https://ayllon.sedelectronica.es/dossier | Trámites sede (timeout frecuente en CI) |
| PLAI Junta CYL (prov. 40, mun. 024) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=024 | Archivo planeamiento aprobado (~4 docs) |

## Cómo se listan expedientes

- **Liferay** en ayllon.es: secciones urbanismo con enlace a transparencia sede; sin biblioteca documental extensa en web.
- **PLAI JCYL** (provincia 40, municipio 024, c_mun 40024): Normas Urbanísticas Municipales (NUM), modificaciones puntuales; documentos vía `openDocumento.do?cDocId=…`.
- **Tablón espublico** (`/board`): tabla HTML Wicket con `preview-document/<uuid>`; mayoría anuncios tributarios; 1 anuncio urbanístico (obligación mantenimiento solares).
- **Transparencia sede**: sección dedicada a urbanismo (sin listado extenso de expedientes en HTML estático).
- **Sin visor municipal** de expedientes ni API JSON de consulta pública.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Trámites disponibles en sede (`/dossier`) con certificado digital; catálogo lento o timeout desde CI.
- Tablón sin licencias de obra publicadas (solo tributos y bandos).
- Estrategia adapter: páginas informativas de trámites + tablón (si aparecen licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM), `urbanismo:plau_cyl_sectores` (24 sectores SU-NC/SUR)
  - Filtro: `n_mun = 'Ayllón'`
  - Campos: `n_titulo`, `n_sector`, `n_num_sect`, `c_id_sect`, `c_plan`, `f_aprob`, `f_bocyl`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson` (EPSG:4326); enriquecer filas PLAI/tablón por coincidencia de nombre de sector.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón con pocos anuncios urbanísticos.
  - Sede `/dossier` con timeout frecuente; requiere `insecure_ssl`.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Sede electrónica con certificado SSL problemático → `insecure_ssl: true`.
- Municipio pequeño (~1200 hab.); volumen bajo de publicaciones urbanísticas activas.
- Portal Liferay Segovia9 (Diputación Segovia); patrón similar a otros municipios segovianos (Abades, Bernuy de Porreros).
- BOCYL: 2 entradas en CSV regional (`boletin_source_id: bocyl`).

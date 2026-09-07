# Arroyo de la Encomienda — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `arroyo-de-la-encomienda` |
| Provincia | Valladolid (CYL código 47, municipio PLAU 008, INE 47008) |
| Boletín | BOCYL (`bocyl`) |
| CMS web | Drupal 9 (`www.aytoarroyo.es`) |
| Sede | Sedipualba (`sede.aytoarroyo.es`) |
| Stub espublico | `arroyodelaencomienda.sedelectronica.es` → «Sede Indeterminada» (no operativa) |

## URLs base y semillas

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aytoarroyo.es | Portal Drupal (urbanismo en `/medio-ambiente-urbanismo-servicios-urbanos`) |
| Sede electrónica | https://sede.aytoarroyo.es | Trámites, tablón, OVT, transparencia |
| Tablón RSS | https://sede.aytoarroyo.es/tablondeanuncios/tablon_rss.aspx | Anuncios BOP/edictos (RSS 2.0, iso-8859-1) |
| Catálogo urbanismo | https://sede.aytoarroyo.es/catalogoservicios.aspx?area=1940&ambito= | Trámites licencia/comunicación urbanística |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=008 | Archivo planeamiento aprobado |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=008 | Planeamiento en información pública |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas `plau_cyl_sectores`, `plau_cyl_planes_parciales`, `plau_cyl_instrumentos_ambito` |

## Expedientes / proyectos

### Tablón Sedipualba (RSS)

- Feed RSS con títulos y fechas; enlaces a `anuncio.aspx?id=…`.
- Ejemplos urbanísticos recientes: edictos BOP aprobación definitiva modificaciones puntuales (mc nº 20–22, sept 2026).
- Sin API JSON; scrape vía RSS + regex de título.

### PlanPublica JCyL

- Tabla HTML estática con instrumentos por municipio.
- Documento indexado: **NORMAS URBANÍSTICAS TERRITORIALES** (PU/NUT, feb 2022, docId 299900).
- Enlaces `openDocumento.do?cDocId=…`.

### IDECyL WFS

- **8 sectores** (`SE-01` … `SE-08`) con geometría MultiPolygon.
- **3 planes parciales** y **1 instrumento de ámbito** con polígonos.
- Campo enlace: `n_num_sect`, `url_doc_info`.

### Web Drupal

- Sección urbanismo con noticias (Sotoverde, inversiones) pero sin listado estructurado de expedientes.
- No hay visor ArcGIS municipal propio.

## Licencias

- **Tablón:** no hay concesiones de licencia de obra en el extracto RSS reciente (sí edictos BOP de modificaciones puntuales PGOU).
- **Catálogo sede:** trámites informativos «Declaración Responsable o Comunicación en Materia Urbanística» e «Instancia General - Urbanismo» (sin registro público de concesiones).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — filtro `n_mun = 'Arroyo de la Encomienda'` → 8 polígonos (SE-01…SE-08)
  - Capas `plau_cyl_planes_parciales` (3) e `plau_cyl_instrumentos_ambito` (1)
  - OutputFormat GeoJSON, srsName EPSG:4326
- **Estrategia:** descarga masiva WFS por municipio; enriquecimiento puntual por código sector (`SE-XX`, `mc nº`) en anuncios tablón/PLAU
- **Limitaciones:** sede Sedipualba sin visor GIS; licencias sin georreferencia; stub espublico indeterminado; web Drupal sin coords por expediente

## Limitaciones

- Dominios `www.arroyodelaencomienda.es` / `.com` no resuelven; portal real es `aytoarroyo.es`.
- Tablón RSS codificado iso-8859-1 (parse con bytes, no UTF-8 estricto).
- PLAI sin filas documentales en el momento de la investigación (solo filtros de trámite).
- Centroide municipal de respaldo: 41.6223, -4.7955 (media WFS sectores).

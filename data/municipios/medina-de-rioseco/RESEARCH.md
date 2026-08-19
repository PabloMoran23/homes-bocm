# Medina de Rioseco — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://medinaderioseco.org/ |
| Urbanismo y Vivienda | https://medinaderioseco.org/urbanismo-y-vivienda/ |
| PGOU | https://medinaderioseco.org/urbanismo-y-vivienda/plan-general-de-ordenacion-urbana/ |
| PECH | https://medinaderioseco.org/urbanismo-y-vivienda/plan-especial-del-casco-historico/ |
| ARU Ciudad de los Almirantes | https://medinaderioseco.org/urbanismo-y-vivienda/aru-medina-de-rioseco/ |
| Unidad AA-12 (normalización) | https://medinaderioseco.org/urbanismo-y-vivienda/proyecto-de-normalizacion-de-fincas-y-proyecto-de-urbanizacion-de-viales-de-la-unidad-aa-12-del-pgou-medina-de-rioseco/ |
| Concentración parcelaria | https://medinaderioseco.org/urbanismo-y-vivienda/plan-de-concentracion-parcelaria/ |
| Formularios / modelos | https://medinaderioseco.org/modelos-de-formularios-y-solicitudes/ |
| Sede electrónica (tablón) | https://medinaderioseco.sedelectronica.es/board |
| PLAI JCYL (docs publicados) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=47&municipio=086 |

## Cómo se listan expedientes

- **WordPress + Elementor**: páginas estáticas bajo `/urbanismo-y-vivienda/` con anuncios de información pública, PDFs vía plugin WP Download Manager (`/download/...`) y enlaces a BOCYL.
- **Sede espublico (Wicket)**: tablón `/board` con tabla HTML (`preview-document` UUIDs). Categorías «Urbanismo» y «Licencias Urbanísticas».
- **PLAI JCYL**: tabla paginada de instrumentos de planeamiento publicados (PECH, ED, PPI, PERI, PN, etc.) con `openDocumento.do`.
- **No hay** visor urbanístico propio del ayuntamiento; el catastro enlaza a sede del Catastro nacional.

## Licencias de obra

- El tablón de la sede publica anuncios bajo «Licencias Urbanísticas» (p. ej. estudios de detalle, urbanizaciones).
- No hay dataset de concesiones con coordenadas; la página de modelos enlaza a formularios generales (SharePoint/urbanismo) sin listado de licencias concedidas.
- El adapter incluye filas del tablón filtradas por licencia + páginas informativas de trámites (sede, modelos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 26 sectores del PGOU de Medina de Rioseco (`n_mun='Medina de Rioseco'`)
  - Capas adicionales: `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`
  - URL ejemplo: `https://idecyl.jcyl.es/geoserver/urbanismo/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=urbanismo:plau_cyl_sectores&CQL_FILTER=n_mun='Medina de Rioseco'&outputFormat=application/json&srsName=EPSG:4326`
  - Campo enlace: `n_num_sect` (p. ej. `SUR-D SR-06`, `SU-NC ST-01`), `c_id_sect`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer filas WP/tablón/PLAI extrayendo códigos de sector (`SURD-SI-01`, `AA-12`, `SUED-I01`, etc.) y consultando WFS por `n_num_sect`.
- **Limitaciones:** sin visor ArcGIS municipal; proyectos de urbanización de calles (Villaesper, San Juan) no tienen polígono en WFS; licencias sin georreferencia; sede requiere `insecure_ssl` (certificado con problemas en cadena).

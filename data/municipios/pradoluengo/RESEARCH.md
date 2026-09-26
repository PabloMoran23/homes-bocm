# Pradoluengo — investigación portal ayuntamiento

**Municipio:** Pradoluengo (Castilla y León, Burgos)  
**Fecha:** 2026-08-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Drupal) | https://www.pradoluengo.es | Portal activo (tema Toools) |
| Normativa | https://www.pradoluengo.es/normativa | Enlace normativa municipal |
| Información general | https://www.pradoluengo.es/informacion-general | Enlaces archivo PLAU CyL JCyL |
| Noticias | https://www.pradoluengo.es/noticias | Avisos (arquitecto técnico, alumbrado DUS 5000) |
| Sede electrónica (espublico gestiona) | https://pradoluengo.sedelectronica.es/board | Tablón de anuncios (~3 filas; empleo + ordenanza) |
| Portal transparencia | https://pradoluengo.sedelectronica.es/transparency | Sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (3 docs, Wicket AJAX) |
| Catálogo trámites | https://pradoluengo.sedelectronica.es/dossier | Trámites sede (lento; sin scrape directo de urbanismo) |
| PLAU CyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=09&municipio=274 | Archivo planeamiento JCyL |
| PLAI CyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=09&municipio=274 | Planeamiento en información pública |
| Índice NUM | https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=291831 | Normas Urbanísticas Municipales (aprobación 2015) |
| OVC Diputación Burgos | https://ovc.diputaciondeburgos.es/ | Visor cartografía provincial (sin enlace expediente) |

## Cómo se listan expedientes

- **PLAU CyL:** documentación oficial del planeamiento (NUM 2015, revisiones parciales 1985–2023). Listado HTML con fechas y tipos de documento.
- **IDECyL WFS:** geometría de instrumentos y sectores publicados en geoportal regional.
- **Tablón sede:** HTML tabla espublico con `preview-document`. Actualmente empleo público y modificación ordenanza reglamentaria; sin expedientes urbanísticos recientes.
- **Drupal noticias:** avisos de citas arquitecto técnico y obras de alumbrado (DUS 5000).
- **Transparencia sede:** sección urbanismo con 3 documentos; contenido cargado por Wicket (no scrapeable sin sesión AJAX).
- **Sin visor municipal** de expedientes ni API JSON de listado histórico.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni tablón.
- Trámites vía sede electrónica (`/dossier`) y citas presenciales arquitecto técnico municipal (noticia web).
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature NUM), `urbanismo:plau_cyl_sectores` (4 sectores: La Esita, Herrería, Barria, Los Llanos Residencial), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'Pradoluengo'`
  - Campo sector: `n_sector`; instrumento: `n_titulo`, `c_plan`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas tablón/noticias por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede sin anuncios urbanísticos recientes.
  - Transparencia urbanismo no scrapeable (Wicket AJAX).
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Tablón sede con pocas filas y sin archivo histórico scrapeable.
- Drupal mezcla noticias urbanísticas con actualidad general (filtros por regex).
- BOCyL ya parseado en pipeline regional (`bocyl`, 3 entradas).

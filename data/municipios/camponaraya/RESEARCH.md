# Camponaraya — investigación portal ayuntamiento

**Municipio:** Camponaraya (Castilla y León, León — El Bierzo)  
**Fecha:** 2026-09-10

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (CMS PSI) | https://camponaraya.es | Portal municipal |
| Tablón de anuncios | https://camponaraya.es/tablon-anuncios | Anuncios con PDFs (concentración parcelaria, planos) |
| Normativa | https://camponaraya.es/normativa-camponaraya | Ordenanzas y normativa municipal (PDFs) |
| Noticias — NNUM | https://camponaraya.es/noticias-listado/761_bando-informativo | Aprobación inicial Normas Urbanísticas Municipales |
| Sede electrónica (espublico) | https://camponaraya.sedelectronica.es/board | Tablón sede (~10 anuncios recientes) |
| Trámites sede | https://camponaraya.sedelectronica.es/dossier | Catálogo de trámites (lento; >45 s) |
| Transparencia — NNUM | https://camponaraya.sedelectronica.es/transparency/3a2d065a-9774-4800-aa3e-b88b8313a8f2/ | Información pública normas urbanísticas |
| JCYL PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=034 | Planeamiento en información pública |
| JCYL PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=034 | Archivo planeamiento aprobado |

## Cómo se listan expedientes

- **Tablón web:** listado paginado (6 páginas) con `<h3>` título + enlace PDF en `/fotos/`. Incluye concentración parcelaria polígono 123, planos y listados.
- **Sede espublico:** enlaces `preview-document` con atributo `title` (sin tabla estructurada en `/board`).
- **Normativa:** lista `<li>` con `<h3>`, fecha y PDF descargable.
- **IDECyL WFS:** instrumentos, sectores y planes parciales con metadatos y geometría.
- **Sin visor municipal** de expedientes ni API JSON de listado histórico.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en tablón ni sede.
- Los trámites de licencia están en el catálogo de la sede (`/dossier`), pero la página tarda mucho en responder.
- Estrategia adapter: páginas informativas de trámites (dossier, board) + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NS), `urbanismo:plau_cyl_sectores` (5), `urbanismo:plau_cyl_planes_parciales` (8)
  - Filtro: `n_mun = 'Camponaraya'` (c_mun INE `24034`, código JCYL `034`)
  - Campos: `n_titulo`, `n_sector`, `n_num_sect`, `url_doc_info`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas tablón/normativa por coincidencia de código sector (SR-1, A-2, SI-III, etc.).
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes.
  - PDFs de concentración parcelaria sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Sede `/dossier` muy lenta (>45 s); `/board` accesible en ~1 s.
- `insecure_ssl: true` en adapter por certificado sede gestionado por espublico.
- Municipio pequeño (~1.800 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).

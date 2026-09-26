# Cidones — investigación portal ayuntamiento

**Municipio:** Cidones (Castilla y León, Soria)  
**INE:** 42061  
**Fecha:** 2026-09-12

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Drupal 7) | https://www.cidones.es | CMS Drupal 7 + tb_megamenu |
| Información urbanística | https://www.cidones.es/informacion-urbanistica | Enlace a archivo PLAU JCyL |
| Modelos de solicitudes | https://www.cidones.es/modelos-de-solicitudes | Formularios licencia obra, declaración responsable, primera ocupación |
| Ordenanzas y reglamentos | https://www.cidones.es/ordenanzas-y-reglamentos | Ordenanza tasas licencias (PDF) |
| PLAU JCyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=061 | Archivo NUM y modificaciones puntuales |
| PLAI JCyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=061 | Documentos en información pública |
| Sede electrónica (espublico) | https://ayuntamientocidones.sedelectronica.es | Responde «Sede Electrónica Indeterminada» sin host correcto; tablón no accesible |

## Cómo se listan expedientes

- **PLAU CyL:** tabla HTML con columnas Libro / Instrumento / Fecha publicación / Fecha acuerdo / Título; enlaces `openDocuIndice.do?cDocId=…` y `ldoc_files.do?cDocId=…`. Códigos provincia 42 (Soria), municipio 061.
- **Web Drupal:** páginas estáticas con enlaces a PDF/DOCX bajo `/sites/cidones.es/files/public/pags/`. Sin listado de expedientes urbanísticos individuales.
- **Sede espublico:** no operativa para scraping (página de selección de sede); sin tablón accesible.

## Cómo se publican licencias

- No hay tablón ni dataset histórico de concesiones de licencia de obra.
- El ayuntamiento publica **modelos normalizados** en `/modelos-de-solicitudes` (solicitud licencia obra, declaración responsable, primera ocupación) y ordenanza de tasas de licencias.
- Estrategia adapter: páginas informativas de trámites (formularios) como filas de licencias con `min_rows: 0` en validación de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `c_mun = '42061'` o `n_mun = 'Cidones'`
  - Resultado: 1 instrumento NUM + múltiples sectores con `MultiPolygon`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer documentos PLAU que mencionan «Sector Nº X» consultando capa de sectores.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni WFS de expedientes de licencia.
  - Sede espublico inaccesible para tablón.
  - Licencias sin georreferencia en portal (solo formularios).
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Drupal 7 sin API JSON; scrape HTML determinista.
- Sede `ayuntamientocidones.sedelectronica.es` no expone tablón (página indeterminada).
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
- Certificado web válido; no requiere `insecure_ssl`.

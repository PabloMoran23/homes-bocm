# Valdetorres de Jarama — Investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.ayto-valdetorresdejarama.es/ |
| Urbanismo (formularios) | https://www.ayto-valdetorresdejarama.es/tramites-y-gestiones/urbanismo |
| Ordenanzas / planeamiento | https://www.ayto-valdetorresdejarama.es/tu-ayuntamiento/normativa/ordenanzas-generales |
| Tablón legacy (web) | https://www.ayto-valdetorresdejarama.es/tu-ayuntamiento/tablon-municipal |
| Sede electrónica | https://valdetorresdejarama.sedelectronica.es/ |
| Tablón oficial (sede) | https://valdetorresdejarama.sedelectronica.es/board |
| Trámites sede | https://valdetorresdejarama.sedelectronica.es/dossier |
| Transparencia sede | https://valdetorresdejarama.sedelectronica.es/transparency |
| Visor SITCM (regional) | https://idem.madrid.org/cartografia/sitcm/html/visor.htm |

**CMS web:** Umbraco (Bootstrap 3, Fontventa S.L.). PDFs en `/media/{id}/{slug}.pdf`.

**Sede:** espublico gestiona (Apache Wicket + YUI). Tablón con tabla AJAX `AdvertisementBoardListPanel`.

## Expedientes / planeamiento

- **No hay registro público de expedientes urbanísticos** en la web municipal; consulta en `/expedientes` requiere Cl@ve/certificado.
- **Instrumento vigente:** Normas Subsidiarias (no PGOU). Modificación puntual documentada en ordenanzas.
- **Formularios urbanismo:** 13 PDFs en página urbanismo (obra mayor/menor, licencias, cédula, segregación, derribo, etc.).
- **Tablón sede:** estructura tabular con expediente, procedimiento, categoría, fecha; vacío en el momento de la investigación.
- **Tablón legacy web:** ~77 PDFs estáticos (`list-group-item`), sin mantenimiento activo; algunos anuncios de información pública antiguos.

## Licencias de obra

- **No hay listado público de licencias concedidas.** Solo formularios de solicitud en web y publicaciones puntuales en tablón cuando procede legalmente.
- El adapter incluye páginas informativas (urbanismo, tablón sede, trámites, transparencia) y formularios PDF como referencia de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='VALDETORRES DE JARAMA'`
  - 15 ámbitos de planeamiento (UE-1..UE-10, SAU-1..SAU-3) con polígonos en EPSG:4326
  - REUR WFS metadata: `vpla:SIUR_V_VPLA` con `CDMUNICIPIO='164'` (26 instrumentos, sin geometría en features)
  - Visor regional SITCM para consulta cartográfica
- **Estrategia:** descarga masiva de ámbitos SITCM como proyectos con `geom_geojson`; enriquecimiento por código UE/SAU en títulos de tablón/PDF cuando hay match.
- **Limitaciones:**
  - Sin visor urbanístico municipal propio
  - Sin geometría de licencias/expedientes individuales
  - Tablón sede vacío (Wicket AJAX; sin filas scrapeables por curl)
  - Catastro municipal sin convenio desde 2020

## Limitaciones generales

- Dominio `valdetorresdejarama.es` no resuelve; usar `ayto-valdetorresdejarama.es`
- Tablón sede requiere sesión Wicket para filas dinámicas; el HTML inicial puede estar vacío
- Licencias individuales solo visibles cuando se publican en tablón (intermitente)

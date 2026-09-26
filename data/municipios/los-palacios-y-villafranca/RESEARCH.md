# Los Palacios y Villafranca — investigación portal ayuntamiento

Municipio: **Los Palacios y Villafranca** (`los-palacios-y-villafranca`)  
Provincia: Sevilla · CCAA: Andalucía · INE: 41091 · BOJA: 1 proyecto parseado

## URLs base y páginas semilla

| Fuente | URL | Tecnología |
|--------|-----|------------|
| Web corporativa | https://www.lospalacios.org | ASP.NET WebForms + tema MasterPorto |
| Urbanismo (índice) | https://www.lospalacios.org/servicios/urbanismo | Secciones PGOU, planeamientos, convenios |
| PGOU (Google Drive) | https://www.lospalacios.org/servicios/urbanismo/pgou | Enlaces a Drive (normas, ordenación, MP 1-14) |
| Planeamientos definitivos | https://www.lospalacios.org/servicios/urbanismo/planeamientos-definitivos | Tabla HTML fecha + título |
| Planeamientos en trámite | https://www.lospalacios.org/servicios/urbanismo/planeamientos-en-tramite | Tabla HTML |
| Convenios definitivos | https://www.lospalacios.org/servicios/urbanismo/convenios-definitivos | Tabla HTML (10 convenios históricos) |
| Convenios en trámite | https://www.lospalacios.org/servicios/urbanismo/convenios-en-tramite | Tabla HTML |
| Sede electrónica | https://lospalacios.sedelectronica.es | espublico gestiona (Wicket/YUI) |
| Tablón de anuncios | https://lospalacios.sedelectronica.es/board/ | Tabla `class_name` / `class_folderCode` |
| Transparencia | https://lospalacios.sedelectronica.es/transparency | Sección «Urbanismo, Obras Públicas y Medio Ambiente» (~131 docs, AJAX) |
| LicytalPub (licencias) | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4106900F | Portal provincial Diputación Sevilla |
| SITUA (PGOU Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41091 | Visor planeamiento Junta de Andalucía |

## Cómo se listan expedientes / proyectos

- **Web municipal:** tablas ASP.NET en subsecciones de urbanismo con columnas fecha (DD-MM-YYYY) + título/objeto. No hay API JSON; scrape determinista de `<tr>/<td>`.
- **PGOU:** documentos alojados en Google Drive (normas urbanísticas, ordenación completa, modificaciones puntuales 1-14).
- **Sede tablón:** filas HTML con clases `class_name`, `class_folderCode`, `class_folderName`, `class_dateFrom`. En la muestra actual (sep 2026) predominan anuncios de personal y presupuesto; sin filas urbanísticas recientes.
- **Transparencia sede:** índice con contador de documentos urbanismo; carga dinámica vía Wicket/AJAX — no scrapeable sin sesión.

## Cómo se publican licencias

- No hay dataset abierto de concesiones de licencia de obra en la web ni en el tablón actual.
- Trámites de licencia vía sede (`/dossier`, `/expedientes` con autenticación Cl@ve/certificado).
- Portal provincial **LicytalPub** (Diputación de Sevilla, CIF P4106900F) para consulta pública de licencias urbanísticas de entidades adheridas.
- El adapter incluye páginas informativas de tablón, sede y LicytalPub (patrón Pozuelo/Tomares).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUA / SituaDIFusión Junta de Andalucía (`cid=41091`): visor JSF de consulta de planeamiento digitalizado; sin API WFS/ArcGIS pública enlazable por expediente.
  - Web municipal: sin visor urbanístico ni capas GeoJSON.
  - Diputación de Sevilla: LicytalPub es listado de licencias, no geometría.
  - Agenda Urbana (agendaurbanalospalacios.org): portal informativo, sin GIS de expedientes.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`manifest.config.centroid`).
- **Limitaciones:** certificado SSL inválido en `www.lospalacios.org` (requiere `insecure_ssl: true`); tablón sin licencias recientes; transparencia sede con carga AJAX.

## Limitaciones generales

- SSL: `www.lospalacios.org` emite certificado con CA no reconocida en el entorno CI.
- Tablón sede: pocas filas visibles (~10) y sin urbanismo en el periodo actual.
- Transparencia: 131 documentos urbanismo accesibles solo tras navegación interactiva en sede.
- PGOU en Google Drive: IDs legacy (`0B_...`) pueden requerir redirección.

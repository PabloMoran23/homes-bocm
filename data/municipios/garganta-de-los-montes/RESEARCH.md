# Garganta de los Montes — investigación portal ayuntamiento

**Municipio:** Garganta de los Montes – El Cuadrón (Comunidad de Madrid)  
**Fecha:** 2026-08-04  
**BOCM regional (referencia):** 9 avisos

## Resumen

Garganta de los Montes combina una **web corporativa WordPress** (`gargantadelosmontes.org`) con
**sede electrónica espublico gestiona** (`gargantadelosmontes.sedelectronica.es`). Los expedientes
de planeamiento activos (Plan Parcial «Los Gargantales») se publican en el **tablón de anuncios**
de la sede. Las licencias se tramitan mediante **impresos PDF** en la web y trámites en la sede;
no hay dataset histórico de concesiones con coordenadas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.gargantadelosmontes.org/` | WordPress | Ordenanzas, impresos, noticias urbanismo |
| Ordenanzas | `https://www.gargantadelosmontes.org/ordenanzas-reglamentos/` | HTML + PDF | Ordenanza 28 títulos habilitantes, tasa licencias urbanísticas |
| Impresos | `https://www.gargantadelosmontes.org/impresos/` | PDF | E-5 licencia obra mayor, E-4 DR obra menor, E-7 ocupación vía |
| Tablón sede | `https://gargantadelosmontes.sedelectronica.es/board` | HTML tabla Wicket | Plan Parcial Los Gargantales (exp. 282/2026), urbanización calle Pez |
| Trámites sede | `https://gargantadelosmontes.sedelectronica.es/dossier` | HTML (lento/JS) | Catálogo trámites con certificado digital |
| Transparencia | `https://www.gargantadelosmontes.org/transparencia/` | WordPress | Presupuesto, plenos; sin carpeta urbanismo dedicada |
| WP REST | `https://www.gargantadelosmontes.org/wp-json/wp/v2/posts` | JSON | Noticias DAE Los Gargantales, rehabilitación casco histórico |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 destacan:

- **Plan Parcial y Proyecto de Reparcelación Urbanización Los Gargantales** — aprobación provisional
  (exp. 282/2026, BOCM 23/07/2026)
- Anuncio previo contrato «Urbanización Calle Pez y Plaza Pocillo» (exp. 212/2026)

## Licencias

- **Impresos web:** formularios E-4 (declaración responsable/obra menor), E-5 (obra mayor),
  E-7 (ocupación vía pública).
- **Ordenanza 4:** tasa por licencias urbanísticas (PDF en ordenanzas).
- **Sede:** presentación electrónica con certificado; catálogo `/dossier` no scrapeable
  de forma estable (respuesta lenta, sin enlaces `/catalog/t/` en HTML inicial).
- No hay listado público de licencias concedidas con ubicación.

## Proyectos / planeamiento

- **Plan Parcial Los Gargantales:** tablón sede + noticias web + DAE (Documento Ambiental
  Estratégico) con PDF en post WordPress.
- **Rehabilitación casco histórico:** noticias municipales sobre obras en casco histórico
  de Garganta y El Cuadrón.
- **Ordenanzas:** Ordenanza 28 títulos habilitantes de naturaleza urbanística (PDF).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - WFS SIT Comunidad de Madrid `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='GARGANTA DE LOS MONTES'` → 0 features
  - Búsqueda `DS_NOMB_AMB ILIKE '%GARGANTAL%'` → 0 features
  - No hay visor urbanístico municipal, ArcGIS ni datos abiertos georreferenciados
- **Estrategia:** El orquestador aplicará centroide municipal + jitter vía `geocode`.
- **Limitaciones:** Tablón y PDFs sin georreferenciación; plan parcial en tramitación sin polígono
  publicado en GIS regional.

## Limitaciones

- Sede `/dossier` tarda >15s y no expone catálogo en HTML estático.
- Tablón muestra solo anuncios recientes (~5 filas).
- WordPress REST accesible; muchas noticias son actividades sociales (filtradas por RE_EXCLUDE).
- Sin histórico BOCM local en web (avisos regionales ya en pipeline BOCM).

## Estrategia adapter

1. Scrape tablón `/board/` (planeamiento Los Gargantales, urbanización).
2. PDFs urbanismo desde ordenanzas e impresos (semillas).
3. WP REST búsquedas: gargantales, plan parcial, casco histórico, DAE.
4. Páginas informativas licencias (impresos + sede + tablón).
5. IDs: `garganta-de-los-montes-{lic|proy}-{sha256[:14]}`.

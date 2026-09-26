# La Puebla de Cazalla — investigación portal ayuntamiento

Municipio: **La Puebla de Cazalla** (`la-puebla-de-cazalla`)  
Provincia: Sevilla · CCAA: Andalucía · INE: **41076** · BOJA: 1 expediente en cola

## URLs base y páginas semilla

| Fuente | URL | CMS / tecnología |
|--------|-----|------------------|
| Web municipal | http://www.pueblacazalla.org/ayto | Joomla (legacy, activo) |
| Sede electrónica | https://lapuebladecazalla.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://lapuebladecazalla.sedelectronica.es/board | espublico gestiona |
| Transparencia | https://transparencia.lapuebladecazalla.es | OpenCMS Diputación Sevilla (SagaSuite) |
| PGOU índice | http://www.pueblacazalla.org/ayto/index.php/la-puebla-de-cazalla/60-ayuntamiento/urbanismo/762-pgou-indice | Joomla |
| Urbanismo | http://www.pueblacazalla.org/ayto/index.php/elayuntamiento/urbanismo | Joomla |
| Indicador transparencia 50 | https://transparencia.lapuebladecazalla.es/es/transparencia/indicadores-de-transparencia/indicador/50.-INSTRUMENTOS-DE-PLANEAMIENTO-URBANISTICO-MUNICIPAL./ | OpenCMS |

**Nota:** `www.lapuebladecazalla.es` no responde (timeout). La web operativa es `pueblacazalla.org/ayto`.

## Proyectos / expedientes urbanísticos

### Tablón sede (`/board`)

HTML tabular con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.  
En septiembre 2026 hay anuncios de **Urbanismo** (categoría) sobre actuación **UR-3** del PGOU (exp. `1584/2023`, procedimiento «Actuaciones Urbanísticas»). Enlaces a `/preview-document/{uuid}`.

### Web Joomla — PGOU

El índice PGOU publica ~15 PDFs del Plan de Ordenación Urbana (PUC 2019, aprobación definitiva BOJA enero 2020):

- Memoria ordenación, participación, normas urbanísticas (partes A-D), catálogo, resumen ejecutivo
- Cartografía temática (encuadre comarcal, usos suelo, estructura…)
- `DefinitivaPgou.pdf` — aprobación definitiva

También hay enlace a artículo «Plan Castillo» y normas urbanísticas en `/ayto/files/normas_urbanisticas_ok3.pdf`.

### Transparencia Diputación Sevilla

Indicador 50 «Instrumentos de planeamiento urbanístico municipal»:

- PDF Normas Subsidiarias
- PDF Adaptación NNSS a LOUA
- Enlace externo al índice PGOU en Joomla

## Licencias de obra

- **No hay dataset público** de licencias concedidas (ni LicytalPub Diputación verificado con CIF).
- El tablón actual (sept. 2026) no contiene licencias de obra; solo empleo público y actuaciones urbanísticas.
- Trámites informativos:
  - Sede `/info` y catálogo de trámites (dossier con redirect loop — no scrapeable)
  - Web Joomla «Ordenación de obras y actividades»
- El adapter devuelve **páginas informativas** de trámites (patrón Pozuelo/Tomares).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SituaDIFusión Junta de Andalucía (`search.jsf`, `cid=41076`) — sin resultados para este municipio
  - Web municipal — PDFs cartográficos sin servicio WMS/WFS
  - Transparencia — solo PDFs estáticos
  - Sede — sin visor SIG enlazado a expedientes
- **Estrategia:** no aplicable; el orquestador usará centroide municipio + jitter
- **Limitaciones:** PGOU en PDF; tablón sin coordenadas; sin ArcGIS/WFS público

## Limitaciones técnicas

- Sede electrónica requiere `insecure_ssl: true` (certificado no verificable en CI).
- `www.lapuebladecazalla.es` inaccesible; usar `pueblacazalla.org`.
- `/dossier` en sede devuelve redirect loop infinito.
- Tablón paginado pero con pocas filas visibles sin autenticación.

## Adapter implementado

`municipio.adapters.la_puebla_de_cazalla:LaPueblaDeCazallaAyuntamientoAdapter`

- `backfill_proyectos`: tablón sede + PDFs Joomla + transparencia + índice PGOU
- `backfill_licencias`: páginas informativas + licencias del tablón si aparecen

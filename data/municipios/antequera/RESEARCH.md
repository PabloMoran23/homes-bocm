# Antequera — investigación portal ayuntamiento

Municipio: **Antequera** (`antequera`), provincia Málaga, Andalucía. INE **29015**.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.antequera.es |
| Tablón general | https://www.antequera.es/ayuntamiento/tablon-de-anuncios/ |
| Tablón Urbanismo (Solr) | https://www.antequera.es/ayuntamiento/tablon-de-anuncios/Urbanismo/ |
| Actividades — Información pública | https://www.antequera.es/ayuntamiento/tablon-de-anuncios/Establecimientos-y-Actividades-Recreativas/Informacion/ |
| PGOU | https://www.antequera.es/normativa/plan-general-de-ordenacion-urbanistica/ |
| Avance SNU | https://www.antequera.es/normativa/avance-de-planeamiento-suelo-no-urbanizable/ |
| Transparencia | https://www.antequera.es/ayuntamiento/transparencia/ |
| Trámites urbanismo | https://www.antequera.es/ayuntamiento/tramites/ |
| Sede espublico | https://antequera.sedelectronica.es/board/ |
| Sede SWAL (Autofirma) | https://sede.antequera.es |

## CMS y listados

- **CMS:** OpenCMS / SAGA Suite (`com.saga.sagasuite.theme.ayto.antequera`).
- **Expedientes urbanísticos:** categoría *Urbanismo* del tablón; listado Solr (`sg-solrlist`, id `solrlisturb-sorting-grid`), paginación `?psolrlisturb=2…8`. Cada ítem: enlace detalle, párrafo descriptivo, fechas inicio/fin en `<time datetime="…">`, PDFs en galería `/export/sites/ayto-antequera/ayuntamiento/tablon-de-anuncios/.galleries/DOCUMENTOS/Urbanismo/`.
- **Códigos expediente:** `YYYY-PROYA######` (planeamiento / actuaciones).
- **Licencias de apertura / actividad:** subsección *Establecimientos y Actividades Recreativas → Información* (`solrlistinfo-sorting-grid`, `?psolrlistinfo=2…10`), expedientes `YYYY-APER######`.
- **PGOU:** páginas estáticas con enlaces PDF/ZIP en galerías OpenCMS (no API).
- **Sede espublico:** tablón HTML clásico (`class_name`, `preview-document`); puede estar vacío o con pocos anuncios.
- **Sede SWAL:** ASP.NET; registro de trámites y enlace al tablón web municipal (no listado masivo de expedientes sin login).

## Licencias

- No hay dataset abierto de concesiones históricas.
- Fuentes: tablón *Información* (aperuras/actividades), páginas informativas de trámites (`/ayuntamiento/tramites/solicitud-de-obras/`, comunicación previa, alta licencia apertura), tablón espublico si publica edictos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - [SITUA Difusión](https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29015): visor regional de planeamiento digitalizado (JSF); sin API GeoJSON/WFS enlazable por código de expediente municipal `PROYA`.
  - Web municipal: mapa estático en menú; sin visor ArcGIS/WFS municipal de expedientes.
  - PGOU: solo PDF/planos, sin servicio REST.
- **Estrategia:** metadatos de proyectos desde tablón + PDF PGOU; geocodificación vía centroide municipio + jitter en orquestador.
- **Limitaciones:** expedientes del tablón no exponen polígono; SITUA no correlaciona automáticamente con `PROYA`/`APER`.

## Limitaciones generales

- Paginación Solr: ~8 páginas urbanismo, ~10 actividades (revisar periódicamente).
- Validez jurídica oficial en BOPMA/BOJA (aviso en tablón).
- `request_delay_s` recomendado por volumen de páginas en backfill.

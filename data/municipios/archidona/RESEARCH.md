# Archidona — investigación portal ayuntamiento

**Municipio:** Archidona (Málaga, Andalucía)  
**Slug:** `archidona`  
**INE:** 29012  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.archidona.es | **Bloqueada** — CloudFront 403 en CI |
| Sede electrónica | https://archidona.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://archidona.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket |
| Portal transparencia | https://archidona.sedelectronica.es/transparency/ | **Operativa** — sin carpetas urbanismo indexables en HTML estático |
| Catálogo trámites | https://archidona.sedelectronica.es/dossier | Muy lenta / timeout en CI |
| Consulta expedientes | https://archidona.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| SITUA / VITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional; sin enlace por expediente ayto |
| Visor PRP Málaga | https://gis.prpmalaga.es/ | Sin REST accesible desde CI |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cártama, Coín, Ronda.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (sep 2026)

| Expediente | Procedimiento | Categoría | Descripción |
|------------|---------------|-----------|-------------|
| 453/2026 | Actuaciones Urbanísticas | Urbanismo | Admisión a trámite proyecto de actuación (BOPMA nº 159, 19/08/2026) |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos o procedimientos de actividad.
- Trámites informativos en sede `/dossier` (timeout en CI) y consulta `/expedientes` (autenticación).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PRP Málaga / Diputación: `gis.prpmalaga.es` (visor cartográfico provincial; sin ArcGIS REST desde CI).
  - SITUA/VITUA (Junta de Andalucía): planeamiento vigente por municipio (INE 29012), sin campo expediente del tablón.
  - No se detectó visor urbanístico municipal público ni WFS/GeoJSON por expediente.
- **Estrategia:** los documentos del tablón son PDF sin georreferencia embebida ni enlace a visor por código de expediente.
- **Limitaciones:**
  - Web municipal bloqueada impide extraer enlaces a visores desde CMS corporativo.
  - Sin WFS/GeoJSON por expediente.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web `archidona.es` no scrapeable (CloudFront WAF).
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia sin carpetas urbanismo con URL directa.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.archidona:ArchidonaAyuntamientoAdapter`
- Fuentes: tablón sede + fila SITUA (PGOU regional) + páginas informativas de trámites.
- IDs: `archidona-lic-*` / `archidona-proy-*` (sha256[:14]).

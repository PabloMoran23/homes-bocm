# Cártama — investigación portal ayuntamiento

**Municipio:** Cártama (Málaga, Andalucía)  
**Slug:** `cartama`  
**Boletín:** BOJA (`boja`, 30 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.cartama.es | **Bloqueada** — CloudFront 403 en CI (incluso con UA navegador) |
| Sede electrónica | https://cartama.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://cartama.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket |
| Portal transparencia | https://cartama.sedelectronica.es/transparency/ | **Operativa** — sección 8. URBANISMO (936 docs, AJAX) |
| Transparencia — innovación PGOU SG-3 | https://cartama.sedelectronica.es/transparency/1a413180-45e2-45fd-aa76-a4420deba94a/ | Carpetas fase (inicial/provisional/definitiva); sin PDFs indexables |
| Transparencia — Plan Especial depuradora | https://cartama.sedelectronica.es/transparency/25e365e8-9ed9-4955-bf57-9af459854bc5/ | **10 documentos** preview-document |
| Catálogo trámites | https://cartama.sedelectronica.es/dossier | Lenta; sin listado histórico |
| Consulta expedientes | https://cartama.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Anuncios urbanismo (web) | https://www.cartama.es/3732/anuncios-e-informacion-publica | Bloqueada (403) |
| Visor PRP Málaga | https://gis.prpmalaga.es/ | Sin REST accesible desde CI |
| SITUA / VITUA (Junta) | https://www.juntadeandalucia.es/.../situa.html | Planeamiento regional; sin enlace por expediente ayto |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Ronda, Griñón.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (jul 2026)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 6796/2023 | Procedimiento Genérico | Información pública cambio de sistema UR-20 |
| 5867/2026 | Certificados o Informes | Citación acreedores (no urbanismo) |

## Transparencia — urbanismo

- **Sección raíz:** «8. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (936 documentos).
- **Subcarpetas:** requieren Wicket AJAX para navegar; no determinista sin sesión.
- **Carpetas semilla** (URLs directas desde BOJA / web urbanismo):
  - Innovación PGOU SG-3 (PP. 1733/2020): subcarpetas de fase sin PDFs listados en HTML estático.
  - Plan Especial depuradora (PP. 1509/2022): memoria, planos situación PGOU, levantamiento topográfico (10 PDFs).

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos o procedimientos de actividad.
- Trámites informativos en sede `/dossier` y departamento urbanismo (presencial 11:00–14:00).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PRP Málaga / Diputación: `gis.prpmalaga.es` (visor cartográfico provincial; sin ArcGIS REST desde CI).
  - SITUA/VITUA (Junta de Andalucía): planeamiento vigente por municipio, sin campo expediente del tablón.
  - Sistema Geográfico Municipal referenciado en procedimientos web (zonificación vectorial al presentar planeamiento); no expuesto públicamente.
- **Estrategia:** los documentos del tablón y transparencia son PDF sin georreferencia embebida ni enlace a visor por código de expediente.
- **Limitaciones:**
  - Web municipal bloqueada impide extraer enlaces a visores desde Drupal/CMS.
  - Sin WFS/GeoJSON por expediente.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web `cartama.es` no scrapeable (CloudFront WAF).
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia: árbol de 936 docs requiere sesión AJAX; solo carpetas semilla con URL directa.
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.cartama:CartamaAyuntamientoAdapter`
- Fuentes: tablón sede + carpetas transparencia configuradas + páginas informativas de trámites.
- IDs: `cartama-lic-*` / `cartama-proy-*` (sha256[:14]).

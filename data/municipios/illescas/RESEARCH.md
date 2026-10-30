# Illescas (Toledo) — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `illescas` |
| INE | 45081 |
| CCAA | Castilla-La Mancha |
| Web corporativa | https://www.illescas.es / http://illescas.es (no accesible desde CI; redirección Apache) |
| Sede electrónica | https://illescas.sedelectronica.es (espublico gestiona, Wicket) |

## Fuentes del portal

### Tablón de anuncios

- URL: https://illescas.sedelectronica.es/board
- Formato: tabla HTML responsive (`data-label` por columna): Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- Enlaces a PDF: `/preview-document/{uuid}`.
- Paginación: solo los ~10 anuncios más recientes visibles sin autenticación; el buscador del tablón redirige a **identificación electrónica** (POST devuelve página de login).

### Portal de transparencia

- URL: https://illescas.sedelectronica.es/transparency
- Carpeta **7. URBANISMO y CONVENIOS URBANISTICOS, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (~650 documentos).
- Navegación por carpetas vía **Wicket AJAX** (`wicketAjaxGet`); no hay URLs estables `/transparency/{uuid}` en el HTML inicial sin sesión AJAX.
- El adapter indexa la sección como catálogo y parsea el tablón cuando hay anuncios urbanísticos.

### Catálogo de trámites

- URL: https://illescas.sedelectronica.es/dossier
- Trámites de urbanismo y vivienda (presentación electrónica). Respuesta lenta; el adapter intenta extraer enlaces con timeout corto.

### Licencias de obra

- No hay listado histórico público de concesiones (solo edictos puntuales en tablón/transparencia).
- Páginas informativas: tablón, dossier y transparencia urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM — `Planeamiento_Municipal/MapServer/0`, filtro `COD_INE='45081'`.
  - Descarga oficial POM: ZIP en `ficheroscomunes.castillalamancha.es/planeamiento/TOLEDO/45081_ILLESCAS.zip`.
- **Estrategia:** query `returnGeometry=true`, `f=geojson`, `outSR=4326` (patrón `albacete.py` / `madrid_ayto_sync.py`). Polígono del **POM municipal** asignado a filas de planeamiento; no hay visor municipal de parcela/expediente enlazable.
- **Limitaciones:**
  - Sin WFS/WMS municipal ni ref. catastral en anuncios del tablón.
  - Búsqueda del tablón requiere login.
  - Web `illescas.es` inaccesible en CI (timeout).
  - Transparencia urbanismo requiere navegación AJAX Wicket (no replicada íntegramente).

## Patrón técnico

- CMS sede: **espublico gestiona** (Apache Wicket), mismo patrón que Móstoles/Morata/Redueña.
- Nomenclatura planeamiento local: **POM** (Plan de Ordenación Municipal), sectores tipo `SUB SO`, `SAU`, modificaciones puntuales (publicadas en DOCM y referenciadas en transparencia).

## Referencias cruzadas

- DOCM / BOP Toledo: anuncios de información pública (modificaciones POM, PAU, reparcelaciones).
- Oficius: https://oficius.es/publicados-por/otros/ayuntamiento-de-illescas-toledo-4638

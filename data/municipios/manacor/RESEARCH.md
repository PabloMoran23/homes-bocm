# Manacor — investigación portal ayuntamiento

Municipio: **Manacor** (`manacor`) — Illes Balears, Mallorca. INE 07033. Sin boletín regional asociado en cola BOCM.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 10) | https://manacor.org |
| Urbanismo (ES) | https://manacor.org/es/urbanismo |
| Urbanisme (CA) | https://manacor.org/ca/urbanisme |
| Normativa / documentos urbanismo | https://manacor.org/ca/urbanisme (PDFs en `/sites/cilma_manacor/files/…`) |
| Noticias RSS | https://manacor.org/es/noticias/rss.xml |
| Sede electrónica (espublico / eadministracio) | https://manacor.eadministracio.cat |
| Tablón de anuncios | https://manacor.eadministracio.cat/board |
| Área Urbanisme (trámites) | https://manacor.eadministracio.cat/citizen-service/9958a625-760e-4915-b506-f0e4acae37d8 |
| Transparencia — enlace web urbanismo | https://manacor.eadministracio.cat/transparency/32805cd0-06d5-40e5-8879-2e8304830f35/ |
| Transparencia — sección 7 Urbanisme (297 docs, árbol AJAX) | https://manacor.eadministracio.cat/transparency |
| PGOU municipal | https://plageneral.manacor.org/ |
| Visor SITMUN | https://sitmun.idelma.cat/urb_manacor → login visor (credenciales embebidas en redirect) |

**Nota:** `manacor.sedelectronica.es` sin tenant devuelve «Sede Electrónica Indeterminada»; el dominio operativo es **eadministracio.cat**.

## Cómo se listan expedientes / planeamiento

### Tablón sede (espublico / Wicket)

HTML en `/board` con filas `<td class="class_name">`, expediente (`class_folderCode`), procedimiento (`class_folderName`), categoría, descripción, fecha (`class_dateFrom` DD/MM/YYYY), enlace `preview-document/{uuid}`.

En la muestra (oct 2026) predominan personal, subvenciones y normativa general; los anuncios de **Actuacions Urbanístiques** son esporádicos.

### Web Drupal — sección Urbanismo

- Noticias recientes enlazadas desde `/es/urbanismo` (obras viarias, ampliación polígono industrial, etc.).
- PDFs estáticos: inventario caminos, decretos IEE, ordenanza informes edificios, guía EPCU, enlaces BOIB.

### Transparencia sede

Subcarpeta enlazada desde la web (`32805cd0-…`) con documentos `preview-document`. El árbol principal incluye **«7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT (297)»** cargado por AJAX (Wicket); no se scrapea el árbol completo en el adapter (solo carpeta semilla + previews directos).

### PGOU

Sitio WordPress `plageneral.manacor.org` con enlace al visor SITMUN; RSS casi vacío (solo entrada por defecto).

## Licencias de obra

No hay listado abierto de licencias concedidas con coordenadas. Fuentes:

1. **Modelos** de comunicación previa en `manacor.org/es/archivos-y-documentos/…`
2. **Sede** — área Urbanisme (llicències, comunicacions prèvies; menú AJAX)
3. **Tablón** — anuncios puntuales cuando se publican

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITMUN IDELMA (`sitmun.idelma.cat/urb_manacor`) — visor con login (usuario `manacor_urb` en redirect; acceso público del formulario devuelve error). Sin endpoint WFS/ArcGIS REST público verificado para expedientes (no existe capa `M033_URBANISME` en ide.idelma.cat como en Pollença M042).
  - PDFs y tablón sin geometría embebida.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:**
  - Visor GIS no integrable sin sesión interactiva SITMUN/DWR.
  - Transparencia masiva (297) requiere navegación AJAX.
  - Consulta de expedientes en sede (`/expedientes`) exige identificación.

## Limitaciones generales

- Dos dominios web (`manacor.org` corporativo, `plageneral.manacor.org` PGOU).
- Sede estable en `eadministracio.cat`; SSL OK.
- RSS noticias limitado (~10 ítems); se complementa con crawl de `/urbanismo`.

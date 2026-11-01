# Tortosa — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www2.tortosa.cat/ |
| Índice urbanismo | https://www2.tortosa.cat/urbanisme/index.php |
| Expedientes por slug | `https://www2.tortosa.cat/urbanisme/?slug=<slug>` (~56 slugs en índice) |
| Trámites (urbanismo) | https://www2.tortosa.cat/tramits/ (enlaces `?codi=97`, `99`, `217`, …) |
| Sede electrónica (AOC) | https://seu-e.cat/es/web/tortosa |
| POUM legacy | https://www.tortosa.cat/webajt/poum2/ |
| Planos municipio | https://www2.tortosa.cat/ciutat/planols.php |

## Proyectos / planeamiento

- CMS propio PHP bajo `/urbanisme/`: menú lateral con `?slug=` (POUM, modificaciones puntuales en trámite, planes parciales, PEUs, proyectos de urbanización, etc.).
- Cada página incluye `#title_page_parent`, `#title_page` y bloques `.element_container` con `.title_element` (fecha `DD/MM/YYYY` + hito) y enlaces PDF (`tortosa-files.synology.me/...` o legacy `tortosa.cat/webajt/...`).
- **Estrategia adapter:** recorrer slugs del índice → parsear `title_element` + primer PDF como `url`/`pdf_url`.
- No hay API JSON ni sede con listado público de expedientes urbanísticos enlazable (consulta vía registro/archivo).

## Licencias de obra

- No se encontró tablón de edictos con concesiones de licencias publicadas (sede seu-e transparencia genérica; trámites telemáticos vía idCAT en Mi espacio personal).
- **Trámites informativos** en `/tramits/` sección Urbanisme: Llicència d'Obra Major/Menor, comunicaciones, certificados, planeamiento derivado (códigos numéricos).
- Adapter: filas informativas con `nota` (sin `fecha_concesion`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Mapa Urbanístico de Catalunya (MUC): https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=43155&set-locale=ca — consulta interactiva POUM/derivados, sin API GeoJSON por código de expediente del portal municipal.
  - Planos PDF estáticos (termino, polígonos) en `/ciutat/planols.php` — sin georreferencia vectorial enlazable a filas del scrape.
  - Documentos PDF del urbanismo — sin coordenadas embebidas parseables de forma fiable.
- **Estrategia:** metadatos desde HTML/PDF links; el orquestador aplicará centroide municipal + jitter. No hay join automático título expediente ↔ capa MUC/WFS en esta fase.
- **Limitaciones:** visor MUC no expone query REST alineada con `title_element`; Synology CDN solo PDFs.

## Limitaciones generales

- Sin boletín regional asociado en cola BOCM (`bocm_count: 0`).
- Crawl ~56 páginas slug + delay 0,35 s (~1–2 min backfill proyectos).
- PDFs en dominio externo Synology (estables en pruebas).

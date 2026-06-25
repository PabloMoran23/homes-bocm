# San Martín de la Vega — investigación portal ayuntamiento

**Municipio:** San Martín de la Vega (Madrid, Comunidad de Madrid)  
**Fecha:** 2026-06-25  
**BOCM regional (referencia):** 21 avisos

## Resumen

El ayuntamiento publica planeamiento y urbanismo en tres frentes complementarios:

1. **Web corporativa WordPress (Divi)** con tablón virtual y biblioteca **WP-Filebase-Pro** de documentos urbanísticos.
2. **Sede electrónica espublico gestiona** (`sanmartindelavega.sedelectronica.es`) con tablón de anuncios en HTML/Wicket.
3. **Portal específico del Avance PGOU** (Weebly) con PDFs del plan general.

No existe visor urbanístico municipal con geometría enlazable por expediente.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón virtual urbanismo | `https://ayto-smv.es/tramites/tablon-virtual/urbanismo-actividades-y-vivienda/` | WordPress + WP-Filebase tree | Estudios de detalle, planes parciales, PGOU, edictos IP, documentación ambiental |
| API WP-Filebase | `https://ayto-smv.es/?wpfilebase_ajax=1&wpfb_action=tree&base={cat_id}` | JSON | Árbol de categorías y PDFs (`/download/urbanismo_actividades_y_vivienda/...`) |
| Tablón sede | `https://sanmartindelavega.sedelectronica.es/board` | HTML tabla Wicket | Anuncios recientes: urbanismo, planeamiento, licencias |
| Inicio sede (extracto) | `https://sanmartindelavega.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios del tablón |
| Catálogo trámites | `https://sanmartindelavega.sedelectronica.es/dossier` | HTML Wicket | Trámites urbanismo/licencias |
| Portal Avance PGOU | `https://plangeneralsanmartindelavega.ayto-smv.es/` | Weebly HTML | Memoria, planos y edictos del avance PGOU (PDF) |
| Impresos licencias | `https://ayto-smv.es/download/descarga_de_instanciassolicitudes/obras_y_otras_autorizaciones/` | PDF estáticos | Formularios de licencia/declaración responsable (no concesiones) |
| Agenda urbana | `https://ayto-smv.es/tramites/tablon-virtual/agenda-urbana/` | WordPress | Normativa y documentación agenda urbana |

## Tablón virtual (WP-Filebase)

Categoría raíz urbanismo: `wpfb-cat-128`. Subcarpetas relevantes:

- Exposición pública de estudios de detalle y planes parciales
- Plan General de Ordenación Urbana
- Exposición pública plan especial parcela SAU-A
- Proyectos expropiatorios y documentación ambiental
- Normas subsidiarias (NNSS)

Cada expediente se organiza en carpeta con PDFs (edicto, anuncio BOCM, memoria, certificado pleno).

## Tablón sede (`/board`)

Tabla con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.

Ejemplos (jun 2026):

- Plan Especial parcela E SAU-A — Categoría Urbanismo / Planeamiento de Desarrollo
- Actas de pleno (referencia indirecta)
- Bajas de padrón (no urbanismo)

Enlaces PDF: `preview-document/{uuid}`.

## Licencias

No hay dataset georreferenciado de concesiones ni listado histórico público.

- Impresos descargables en la página de urbanismo (licencia de obras, declaración responsable, etc.).
- Anuncios de licencia en tablón sede cuando se publican edictos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal (ArcGIS/WFS) ni enlace expediente→polígono en el portal. El Visor SIT de la Comunidad de Madrid (`idem.madrid.org`) tiene planeamiento aprobado definitivamente a escala municipal, pero no enlaza con códigos de expediente del ayuntamiento.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`coord_source: municipio_centroid_jitter`).
- **Limitaciones:** Documentación en PDF/planos raster; PGOU en Weebly sin API GIS; sede con certificado SSL de CA no estándar (`insecure_ssl: true`).

## Limitaciones

- Certificado SSL sede: requiere `insecure_ssl: true` en el adapter.
- WP-Filebase: árbol AJAX sin metadatos de fecha estructurados (fecha inferida del título/URL).
- Tablón sede: ~10 anuncios recientes visibles; histórico completo requiere búsqueda Wicket POST (no implementado).
- Licencias: solo formularios informativos + edictos puntuales en tablón.

## Estrategia adapter

1. Crawl recursivo WP-Filebase desde categoría 128 → proyectos (PDFs urbanismo).
2. Scrape portal PGOU Weebly (páginas avance/documentos) → proyectos PGOU.
3. Tablón sede `/board` + extracto `/info.0` → proyectos y licencias filtrados por keywords.
4. Impresos `/download/.../obras_y_otras_autorizaciones/` → licencias informativas.
5. IDs: `smv-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico + SSL: `pelabravo.py`
- Tablón sede HTML: `mostoles.py`, `ciempozuelos.py`
- Impresos informativos: `pozuelo.py`

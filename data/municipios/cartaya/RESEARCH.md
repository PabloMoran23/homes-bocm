# Cartaya — investigación portal ayuntamiento

**Municipio:** Cartaya (Huelva, Andalucía)  
**Slug:** `cartaya`  
**BOJA:** `boja` (2 entradas en CSV)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Drupal 7) | https://www.cartaya.es | Área de Urbanismo, normativa, noticias |
| Urbanismo (área municipal) | http://cartaya.es/areas-municipales?area=urbanismo | Descripción del área (sin listado dinámico) |
| Instrumentos urbanísticos | https://www.cartaya.es/es/normativa/instrumentos-urbanisticos | Formulario de búsqueda por tipo de normativa (Wicket/AJAX) |
| Agenda Urbana | https://www.cartaya.es/es/areas-municipales/agenda-urbana | PDF `agendaurbanacartaya.pdf` |
| Noticias urbanismo | https://www.cartaya.es/es/areas-municipales/noticias/urbanismo | ~12 noticias recientes de actuaciones urbanísticas |
| Tablón web (Drupal) | https://www.cartaya.es/es/tablon-de-anuncios | Redirige/enlaza a sede |
| Sede electrónica (espublico) | https://cartaya.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://cartaya.sedelectronica.es/board/ | Edictos HTML tabla (~10 visibles) |
| Transparencia | https://cartaya.sedelectronica.es/transparency/ | Carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (2115 docs, Wicket AJAX) |
| Trámites | https://cartaya.sedelectronica.es/dossier | Catálogo de trámites (timeout ocasional en CI) |
| SITUA (Junta de Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta PGOU/planeamiento regional |

**Nota SSL:** `cartaya.sedelectronica.es` presenta certificado con CA no reconocida en CI; el adapter usa `insecure_ssl: true`.

## Cómo se listan expedientes / proyectos

1. **Drupal:** páginas estáticas y noticias con enlaces a PDF en `/sites/default/files/`. El buscador de instrumentos urbanísticos en `/es/normativa/instrumentos-urbanisticos` es un formulario sin listado HTML estático (requiere interacción Wicket).
2. **Noticias urbanismo:** listado HTML en `/es/areas-municipales/noticias/urbanismo` con enlaces a fichas `/es/noticias/{slug}`.
3. **Tablón espublico:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Solo ~10 filas en primera página.
4. **Transparencia sede:** carpeta «7. URBANISMO…» con 2115 documentos; requiere sesión Wicket AJAX para expandir subcarpetas (no UUID estático en HTML inicial).

## Cómo se publican licencias

- **No hay listado histórico público** de licencias concedidas en el portal municipal.
- El tablón sede publica ocasionalmente edictos de urbanismo (p. ej. cesión administrativa de licencia de bar en feria); la mayoría de filas visibles son empleo/convocatorias.
- Trámites de licencia vía sede (`/dossier`, `/expedientes`) requieren identificación.
- Formularios de instancias en web Drupal (`/es/tramites/descarga-de-documentos`).
- El adapter devuelve páginas informativas del tablón, catálogo de trámites y licencias detectadas en tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - No hay visor urbanístico municipal (ArcGIS, GeoJSON, WFS) enlazado desde cartaya.es.
  - `cartaya-publicform.incidenciasurbanas.com` es formulario de incidencias urbanas, sin capas GIS.
  - SITUA (Junta de Andalucía): portal JSF de consulta de planeamiento; sin API/WFS pública enlazable por código de expediente.
  - Callejero web (`/es/conoce/callejero`) sin geometría de expedientes.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** solo PDFs y noticias sin georreferencia; tablón sin coordenadas; transparencia urbanismo vía Wicket AJAX; consulta de expedientes autenticada.

## Limitaciones

- Certificado SSL inválido en sede electrónica.
- Tablón sede: paginación Wicket no scrapeada (solo primera página).
- Transparencia urbanismo: requiere AJAX Wicket para listar 2115 documentos.
- Instrumentos urbanísticos: buscador interactivo sin listado estático.
- Web municipal puede devolver HTTP 429 con User-Agent no estándar (usar Mozilla UA).
- Sin listado público de licencias históricas.

## Referencias de patrón

- **Lepe** (`lepe.py`): Drupal + espublico tablón (mismo provincia, Huelva).
- **Conil de la Frontera** (`conil_de_la_frontera.py`): espublico tablón + web municipal.
- **Tomares** (`tomares.py`): espublico + enlace SITUA como metadata PGOU.

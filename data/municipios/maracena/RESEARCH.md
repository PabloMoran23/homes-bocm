# Maracena (Granada) — investigación portal urbanismo

## Web oficial y sede

- **Web:** https://maracena.es/ (WordPress; el endpoint `/wp-json/wp/v2/posts` responde **401** sin sesión).
- **Menú Urbanismo:** https://maracena.es/tematicas/urbanismo/normas-subsidiarias/
- **Sede electrónica (espublico gestiona):** https://maracena.sedelectronica.es/
  - **Tablón de anuncios:** https://maracena.sedelectronica.es/board/
  - **Trámites (dossier):** https://maracena.sedelectronica.es/dossier
  - **Transparencia:** https://maracena.sedelectronica.es/transparency

## Cómo se listan expedientes / publicaciones

| Fuente | Formato | Notas |
|--------|---------|-------|
| Tablón sede | HTML tabla (Wicket): celdas `class_name`, `class_folderCode`, … | Algún contenido urbanístico (edictos); muchas filas son convocatorias/BOP no urbanísticas — el adapter filtra por palabras clave. |
| Web WordPress | **RSS por categoría** (el adapter no usa REST por 401) | Categorías semilla: `/category/urbanismo/feed/`, `proyectos`, `reparcelaciones`, `arquitectura`. |
| Página temática urbanismo | HTML + enlaces a PDF y recursos externos | Se siguen enlaces `.pdf` y dominios relevantes cuando el título/contexto encaja. |

## Licencias de obra

- No aparece un listado tabular de licencias concedidas descargable en abierto: el flujo habitual es **tramitación vía sede** (`/dossier`) y **publicación de edictos/notificaciones** en el **tablón**.
- El adapter incluye filas informativas (tablón, trámites, transparencia, temática urbanismo) y cualquier fila del tablón que coincida con patrón de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Motivo:** No se ha localizado en el portal municipal un **visor urbanístico municipal** con capas descargables por expediente (WFS/ArcGIS público enlazado) ni geometría embebida en los listados analizados. La **Junta (SITUA)** ofrece consulta de planeamiento a escala autonómica, no delimitación por expediente municipal enlazable de forma estable desde el scrape.
- **Fuentes consultadas:** web temática urbanismo, tablón sede, enlace informativo SITUA (`https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf`).
- **Estrategia adapter:** sin `geom_geojson`; el orquestador aplica **centroide municipal + jitter** vía `geocode` (centroide IGN en `manifest`).

### Limitaciones

- WordPress **REST deshabilitado** para anónimos; la ingesta de noticias usa **RSS** (hasta ~10 ítems recientes por categoría en la práctica).
- Tablón sede: mezcla de convocatorias/empleo; requiere filtrado por keywords.
- Sin geometría por expediente en esta integración.

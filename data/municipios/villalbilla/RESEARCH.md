# Villalbilla — investigación portal ayuntamiento

**Fecha:** 2026-06-19  
**Slug:** `villalbilla`  
**BOCM regional (referencia):** 46 filas

## Resumen

Villalbilla publica urbanismo y licencias en **dos portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://villalbilla.es | WordPress (Astra) | Noticias Vivienda y Urbanismo, PDFs trámites, REST API |
| Sede electrónica | https://aytovillalbilla.sedelectronica.es | espublico (Wicket) | Tablón anuncios, transparencia, trámites |

## Fuentes de proyectos / expedientes

### 1. WordPress — categoría Vivienda y Urbanismo

- **Categoría:** https://villalbilla.es/category/areas/vivienda-y-urbanismo/ (REST: `categories=3316`, ~19 posts)
- **RSS:** https://villalbilla.es/category/areas/vivienda-y-urbanismo/feed/
- **REST API:** `https://villalbilla.es/wp-json/wp/v2/posts?categories=3316&per_page=100`

Contenido: noticias de planeamiento (normas subsidiarias), plenos, concesiones de licencia publicadas, promociones de vivienda, comunicados sobre proyectos energéticos. Algunos posts incluyen PDFs en `wp-content/uploads/`.

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://aytovillalbilla.sedelectronica.es/board
- **Formato:** tabla HTML espublico (`AdvertisementBoardListPanel`) con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- **Filtro urbanismo:** categoría «Urbanismo», procedimientos tipo «Planeamiento de Desarrollo».
- **Estado 2026-06-19:** plataforma en **mantenimiento** («En mantenimiento» en toda la sede). El adapter intenta el tablón y continúa con WordPress si no responde.

### 3. Portal transparencia (sede)

- Enlaces desde web: `aytovillalbilla.sedelectronica.es/transparency/{uuid}/`
- Documentos urbanísticos enlazados desde noticias WP (p. ej. recursos de alzada contra plantas fotovoltaicas).

## Fuentes de licencias

1. **Noticias WP** con «Concesión de Licencia de Obras» (p. ej. 102 viviendas El Viso, 63 viviendas El Viso).
2. **Área urbanismo:** https://villalbilla.es/areas/vivienda-y-urbanismo/ — PDFs informativos:
   - `LICENCIA-URBANISTICA-FORM.pdf`
   - `TRAMITES.pdf`
3. **Tablón sede** (cuando operativo): anuncios de licencia/disciplina en categoría Urbanismo.

No hay listado público de concesiones con coordenadas (`lat`/`lon`/`distrito` no disponibles).

## Limitaciones

- Sede espublico **inaccesible** por mantenimiento (2026-06-19); tablón y transparencia no scrapeables hasta restablecimiento.
- WordPress solo indexa noticias recientes (~19 en categoría urbanismo); histórico BOCM no duplicado aquí.
- Sin API REST de expedientes urbanísticos estructurados.
- Licencias sin geolocalización en fuentes públicas.

## Estrategia adapter

1. **proyectos.jsonl:** REST API categoría 3316 + PDFs del área urbanismo; tablón sede cuando disponible.
2. **licencias.jsonl:** posts WP con regex licencia + PDFs trámites del área urbanismo + tablón sede cuando disponible.

# Bigastro — investigación portal ayuntamiento

Municipio: **Bigastro** (`bigastro`) — Provincia de Alicante, Comunitat Valenciana.  
INE: **03044**. Boletín: **DOGv** (1 expediente parseado en histórico).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://bigastro.es | WordPress 7.4 + Elementor (Plesk) |
| Concejalía Urbanismo | https://bigastro.es/concejalias-areas/urbanismo/ | HTML estático |
| Anuncios / noticias | https://bigastro.es/anuncios/ | WordPress posts |
| Sede electrónica | https://bigastro.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://bigastro.sedelectronica.es/board | HTML tabla `class_name` |
| Trámites | https://bigastro.sedelectronica.es/dossier | Catálogo procedimientos (SPA) |
| Transparencia — normativa | http://bigastro.sedelectronica.es/transparency/48fff066-bc03-438c-9082-9cdd753bc98d/ | Ordenanzas y tasas urbanísticas (PDF preview) |
| Transparencia — urbanismo | https://bigastro.sedelectronica.es/transparency/f9b557fd-a52e-47bc-ac52-5a8b7e932d79/ | Sección transparencia |
| Diputación Alicante (presupuesto) | http://documentacion.diputacionalicante.es/presupuesto.asp?municipio=44 | Referencia externa (código mun. 44) |

## Cómo se listan expedientes / proyectos

1. **Tablón sede (espublico):** tabla HTML con columnas `class_name`, `class_folderCode` (expediente), `class_folderName` (procedimiento), `class_description`, `class_dateFrom`. Enlaces a `/preview-document/<uuid>`. ~10 filas visibles (histórico limitado en página).
2. **WordPress:** REST API restringida (`rest_not_logged_in`). Se usa **wp-sitemap-posts-post-1.xml** para descubrir URLs de noticias/anuncios con keywords urbanísticas (obras, polígono industrial, BOP, urbanismo).
3. **Transparencia:** listado de ordenanzas/tasas con enlaces `preview-document` (licencias urbanísticas, construcciones, cédulas urbanísticas).
4. **No hay** visor urbanístico municipal ni listado público de expedientes urbanísticos (consulta en `/expedientes` requiere Cl@ve).

## Cómo se publican licencias

- **Tablón:** edictos puntuales si el ayuntamiento los publica (p. ej. enajenación parcela, alteraciones de bienes).
- **Trámites sede:** licencias de obra/comunicación previa vía catálogo `dossier` (sin histórico público descargable).
- **No hay** dataset abierto de licencias concedidas ni listado masivo como Madrid SIGMA.

El adapter incluye páginas informativas de trámites (patrón Pozuelo/Benigànim) cuando no hay licencias históricas publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro municipal: `cod_ine_mun=03044`
  - Capas encontradas: `Plan general` (exp. 20001482) y `MODIFICACIÓN PUNTUAL N. 4 DEL PLAN GENERAL` (exp. 20040196), ambas con polígono GML.
- **Estrategia:** descarga WFS por `startIndex` (offsets 0–16000), match por keywords en título (`plan general`, `modificación`, `pgou`). Enriquecimiento en `_fetch_geometry()`.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en tablón.
  - WFS solo cubre zonificación planeamiento (no licencias ni expedientes individuales del tablón).
  - REST WP bloqueada; geometría no disponible por post.
  - Filas del tablón (p. ej. enajenación parcela) no tienen polígono asociado en portal.

## Limitaciones generales

- Histórico tablón corto (~10 documentos en página actual).
- `dossier` y `expedientes` son SPA/autenticados — no scrapeables sin login.
- Provincia en cola CSV aparece como "Bigastro" (dato fuente); manifest usa **Alicante**.
- SSL sede válido; no requiere `insecure_ssl` pero se mantiene por consistencia con adapters CV.

## Referencias de implementación

- Tablón espublico: `municipio/adapters/beniganim.py`, `municipio/adapters/altea.py`
- WP + sede: `municipio/adapters/venturada.py`
- WFS ICV geometría: `municipio/adapters/canals.py`

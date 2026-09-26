# La Puebla de los Infantes — investigación portal ayuntamiento

**Municipio:** La Puebla de los Infantes (`la-puebla-de-los-infantes`)  
**Provincia:** Sevilla · **CCAA:** Andalucía · **INE:** 41078 · **Boletín:** BOJA

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (OpenCMS / Alkacon) | https://www.lapuebladelosinfantes.es |
| Sede electrónica (GSede / INPRO) | https://sede.lapuebladelosinfantes.es |
| Tablón electrónico INPRO | https://sede.lapuebladelosinfantes.es/tablon-1.0/do/entradaPublica?ine=41078 |
| Transparencia ITA 2014 | https://www.lapuebladelosinfantes.es/es/transparencia |
| Noticias / anuncios | https://www.lapuebladelosinfantes.es/es/actualidad/noticias/ |
| SITUA (Junta Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41078 |

## Cómo se listan expedientes / planeamiento

1. **Tablón INPRO (`tablon-1.0`)** — Sede propia del municipio (mismo stack que Diputación Sevilla / INPRO). Formulario POST a `/tablon-1.0/do/anuncio/listado` con sesión; categorías en `<select>` (Urbanismo = `opcionMenuIzda=5`). Filas en `<tr class="odd|even">` con celdas ocultas (`referencia`, `asunto`, URL documento). **Estado actual (2026-09): tablón vacío** (0 anuncios en todas las categorías).
2. **Noticias OpenCMS** — Anuncios y ordenanzas publicados como noticias con PDFs en `/export/sites/puebladelosinfantes/.galleries/documentos-noticias/`. Ejemplo urbanístico: *Regulación de la tasa por expedición de la resolución de Asimilado a Fuera de Ordenación* (2 PDFs BOP + texto ordenanza).
3. **Transparencia ITA** — Sección E «Urbanismo» con indicadores enlazados (`…-00049/`). Los enlaces aparecen en la página principal de transparencia pero las URLs individuales de indicador devuelven **404 OpenCms** (indicadores no publicados / sin documentos).
4. **SITUA** — Búsqueda por INE 41078: **sin instrumentos de planeamiento** digitalizados.

## Cómo se publican licencias

- No hay visor ni listado público de licencias concedidas.
- El tablón INPRO admite categoría «Urbanismo» pero está vacío.
- La sede ofrece trámite por ticket GSede (área `URBANISMO`) sin listado de resoluciones.
- **Estrategia adapter:** páginas informativas (tablón, sede urbanismo) + filas del tablón si aparecen en el futuro.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - SITUA (Junta Andalucía, INE 41078): sin capas ni instrumentos.
  - Web / sede / transparencia: sin visor ArcGIS, WFS ni GeoJSON.
  - Tablón y noticias: solo PDFs sin georreferencia.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** municipio pequeño sin SIG municipal público; planeamiento no depositado en SITUA.

## Limitaciones

- Tablón INPRO requiere sesión (cookie jar) y POST al listado; vacío en el momento de la investigación.
- Indicadores de transparencia ITA enlazados pero no resuelven (404).
- Sin licencias publicadas; solo trámites informativos.
- SSL de sede válido; no requiere `insecure_ssl`.

## Referencia de patrón

Similar a **Almensilla** (`municipio/adapters/almensilla.py`): OpenCMS + tablón INPRO DipSevilla/INPRO.

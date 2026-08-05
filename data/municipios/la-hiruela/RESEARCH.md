# La Hiruela — investigación portal ayuntamiento

**Municipio:** La Hiruela (Comunidad de Madrid)  
**Fecha:** 2026-08-03  
**BOCM regional (referencia):** 11 avisos

## Resumen

La Hiruela es un municipio muy pequeño de la Sierra Norte de Madrid. La web oficial es
**ayuntamientolahiruela.es** (WordPress + OceanWP). La **sede electrónica** (`lahiruela.sedelectronica.es`)
usa la plataforma **espublico gestiona** con tablón de anuncios y portal de transparencia básico.
La normativa urbanística (NNSS, ordenanzas de edificios y estética) se publica como **PDF en la página
Ayuntamiento**. El programa **DUS5000** tiene página propia con el proyecto integral municipal.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://ayuntamientolahiruela.es/ayuntamiento/` | WordPress HTML + PDF | Ordenanzas urbanísticas, NNSS, evaluación de edificios, condiciones estéticas |
| DUS5000 | `https://ayuntamientolahiruela.es/dus5000/` | WordPress + PDF | Proyecto integral La Hiruela (marzo 2026) |
| Tablón anuncios | `https://lahiruela.sedelectronica.es/board` | HTML tabla Wicket | ~4 anuncios recientes (cobranza, bandos, contratación obra) |
| Portal transparencia | `https://lahiruela.sedelectronica.es/transparency` | HTML estático | Enlace a tablón; sin catálogo urbanismo scrapeable |
| Sede info | `https://lahiruela.sedelectronica.es/info.0` | Redirect | Mismo tablón que `/board` |

**Nota:** `www.lahiruela.es` no responde; el dominio activo es `ayuntamientolahiruela.es`.

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (visor PDF). En agosto 2026 muestra ~4 anuncios (IAE, incendios,
calendario fiscal, adjudicación proyecto embellecimiento área recreativa Huerto del Cura).

## Licencias

- No hay dataset histórico de concesiones con coordenadas.
- Trámites de licencia no aparecen en catálogo `/dossier` (redirige a web municipal).
- Anuncios de obra/licencia aparecen en tablón cuando se publican (p. ej. contratación con dirección
  de obra).

## Proyectos / planeamiento

- **Ayuntamiento:** PDFs de modificaciones NNSS, aprobaciones BOCM, ordenanza evaluación de
  edificios, condiciones estéticas, reglamento definitivo.
- **DUS5000:** Proyecto integral municipal (`PROYECTO-INTEGRAL_LA-HIRUELA_signed.pdf`, 2026).
- **Tablón:** Adjudicación redacción proyecto + dirección obra embellecimiento área recreativa
  (expediente 2/2026).
- **Embellecimiento viario:** PDF en página ayuntamiento (2025).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal, ArcGIS ni datos abiertos georreferenciados.
  Consulta WFS `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='LA HIRUELA'` devuelve **0 ámbitos**.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** Solo PDFs y tablón sin georreferenciación; municipio sin planeamiento
  digitalizado en SITCM.

## Limitaciones

- WordPress REST API no expone páginas de urbanismo por búsqueda (`search=urbanismo` → 0).
- Sede `/dossier` redirige a la web municipal; sin catálogo de trámites scrapeable.
- Tablón muestra solo anuncios recientes (~4 filas); histórico no paginado.
- Dominio `lahiruela.es` inactivo; usar `ayuntamientolahiruela.es`.

## Estrategia adapter

1. Scrape PDFs urbanismo desde `/ayuntamiento/` (filtro NNSS, planeamiento, embellecimiento).
2. PDF proyecto integral desde `/dus5000/`.
3. Scrape tablón `/board` + `/info.0` (tabla + fallback enlaces).
4. Páginas informativas licencias (tablón, transparencia, ordenanzas).
5. IDs: `la-hiruela-{lic|proy}-{sha256[:14]}`.

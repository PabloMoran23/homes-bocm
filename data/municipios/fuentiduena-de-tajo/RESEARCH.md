# Fuentidueña de Tajo — investigación portal ayuntamiento

**Municipio:** Fuentidueña de Tajo (Comunidad de Madrid)  
**Slug:** `fuentiduena-de-tajo`  
**Fecha:** 2026-08-13  
**BOCM regional (referencia):** 4 avisos

## Resumen

Fuentidueña de Tajo publica información municipal en **WordPress** (`fuentiduenadetajo.org`, tema
«ayuntamiento» con widgets LivingStore) y anuncios administrativos en la **sede electrónica espublico
gestiona** (`fuentiduenadetajo.sedelectronica.es`). No hay visor urbanístico municipal propio; la
geometría de ámbitos del PGOU está en el **SIT de la Comunidad de Madrid** (WFS público).

Dominio `.es` (`fuentiduenadetajo.es`) no responde; redirige a `.org`.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://www.fuentiduenadetajo.org` | WordPress | Avisos, noticias, normativas, documentos |
| Avisos (tablón web) | `https://www.fuentiduenadetajo.org/avisos/` | CPT lsvrnotice + sitemap | Avisos municipales (mayoría no urbanismo) |
| Documentos | `https://www.fuentiduenadetajo.org/documentos/` | CPT lsvrdocument + RSS | PDFs descargables (deportes, cultura, concentración parcelaria) |
| Tablón de anuncios | `https://fuentiduenadetajo.sedelectronica.es/board` | HTML tabla Wicket | Edictos, ordenanzas, padrón |
| Portal transparencia | `https://fuentiduenadetajo.sedelectronica.es/transparency/` | Wicket AJAX | Sección 7: Urbanismo (17 docs) — requiere sesión |
| Trámites sede | `https://fuentiduenadetajo.sedelectronica.es/info.0` | espublico | Catálogo trámites (sin listado concesiones) |
| Consulta expedientes | `https://fuentiduenadetajo.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 24 ámbitos PGOU (UA-*, S-*) |

Páginas `normativas/` y `reguladoras/` existen pero no indexan PDFs urbanísticos descargables
(solo navegación).

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Estado jul 2026: 3 anuncios (padrón, herederos, ordenanza fiscal cultural) — sin urbanismo activo.
Cuando haya licencias o exposiciones públicas aparecerán aquí (patrón espublico estándar).

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón cuando el procedimiento sea *Licencias Urbanísticas*.
- Consulta de expedientes en sede requiere Cl@ve.
- Web no expone formularios de licencia descargables en sección urbanismo dedicada.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
  — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='FUENTIDUEÑA DE TAJO'`.
  24 ámbitos: UA-02…UA-16, S-01.R EL LOMERON, etc. (polígonos EPSG:4326).
- **Estrategia:** Enriquecer proyectos cuyo título mencione código de ámbito (UA-*, S-*)
  o nombre de sector vía query WFS ILIKE; sin visor municipal ni enlace expediente→polígono.
- **Limitaciones:** Tablón sin georreferenciación; transparencia urbanismo (17 docs) tras AJAX Wicket;
  expedientes tras login; sin ArcGIS/GeoJSON en portal del ayuntamiento.

## Proyectos urbanísticos localizados

- Noticia WP: «Mejora del entorno urbanistico en Avenida Elena Soriano y Polideportivo Justo Terrés»
- Noticia WP: «Bando Limpieza y Vallado de Parcelas Urbanas»
- Documento WP: «Concentración Parcelaria de la Zona Regable de La Poveda»

## Limitaciones

- Tablón muestra pocos anuncios recientes; histórico requiere paginación Wicket.
- Portal transparencia urbanismo (17 docs) no scrapeable sin tokens de sesión.
- Avisos web mezclan empleo, fiestas, premios académicos (filtrados por regex).
- `fuentiduenadetajo.es` no resuelve; canonical en `.org`.

## Estrategia adapter

1. Scrape tabla tablón `/board` (parser `data-label`).
2. WP REST posts (búsqueda urbanismo/planeamiento) + sitemap avisos + RSS documentos.
3. Páginas informativas licencias: tablón, consulta expedientes, trámites sede.
4. Geometría WFS SIT cuando el título contenga código UA-/S- o nombre de ámbito.
5. IDs estables: `fuentiduena-de-tajo-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `perales_de_tajuna.py`, `torrejon_de_velasco.py`
- WP + WFS SIT partial: `villarejo_de_salvanes.py`

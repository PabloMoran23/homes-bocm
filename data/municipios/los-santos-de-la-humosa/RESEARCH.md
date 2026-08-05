# Los Santos de la Humosa — investigación portal ayuntamiento

Municipio: **Los Santos de la Humosa** (`los-santos-de-la-humosa`) — Comunidad de Madrid, boletín BOCM (11 entradas).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://lossantosdelahumosa.eu | WordPress Avada (PHP 8.0) |
| Bando (WP REST) | https://lossantosdelahumosa.eu/wp-json/wp/v2/posts?categories=31 | Noticias/bandos municipales (121 posts) |
| Nota informativa | https://lossantosdelahumosa.eu/wp-json/wp/v2/posts?categories=117 | Avisos generales (507 posts) |
| Sede electrónica | https://lossantosdelahumosa.sedelectronica.es | espublico gestiona (eHome) |
| Tablón anuncios | https://lossantosdelahumosa.sedelectronica.es/board | Tabla HTML con preview-document PDF (~10 filas) |
| Transparencia | https://lossantosdelahumosa.sedelectronica.es/transparency/ | Portal Wicket (secciones por UUID) |
| Consulta expedientes | https://lossantosdelahumosa.sedelectronica.es/expedientes | Requiere Cl@ve (no listado público) |
| Trámites | https://lossantosdelahumosa.sedelectronica.es/dossier | Catálogo Wicket (timeout en CI) |

## Cómo se listan expedientes / proyectos

1. **WordPress REST** — categorías `bando` (id 31) y `nota-informativa` (id 117): noticias de NNSS (Sector 3, Sector 8), publicaciones BOCM, obras municipales.
2. **Búsqueda WP** — términos `planeamiento`, `nnss`, `normas subsidiarias`, `sector`, `bocm`.
3. **Tablón sede** — tabla con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Solo ~10 anuncios visibles (sin paginación). En la investigación (ago 2026) predominan subvenciones y bandos generales; sin filas categoría Urbanismo.
4. **Transparencia sede** — secciones enlazadas desde la web (`/transparency/{uuid}/`); navegación Wicket/AJAX, no scrapeable de forma determinista.

## Cómo se publican licencias

- **Tablón sede** (`/board`): publica licencias urbanísticas cuando el ayuntamiento las anuncia (preview-document PDF).
- **No hay dataset abierto** de concesiones históricas ni listado CSV.
- Trámites informativos en sede (`/dossier`, `/expedientes`) requieren autenticación o cargan vía Wicket.
- Páginas informativas de trámites incluidas como filas de referencia (patrón Loeches/Móstoles).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='LOS SANTOS DE LA HUMOSA'`
  - 19 ámbitos: UE-1..UE-12, S-1 EL QUEMADO, S-2 LA SOLEDAD, S-3 LOS LLANOS, S-4 CAMINO DE ANCHUELO, S-5 ROBLEDAL, S-6 LOS LLANOS-INDUSTRIAL (APLAZADO), S-7 MAGDALENA INDUSTRIAL (APLAZADO), S-8 HENARES (APLAZADO)
- **Estrategia:** query WFS por código ámbito (UE-N, S-N) vía `municipio.gis.sitcm`; mapeo explícito Sector N en títulos NNSS → S-N (p. ej. Sector 3 → S-3 LOS LLANOS, Sector 8 → S-8 HENARES).
- **Limitaciones:**
  - No hay visor urbanístico propio del ayuntamiento ni enlace expediente→polígono.
  - SITCM cubre ámbitos de planeamiento, no parcelas de licencias individuales.
  - Títulos genéricos («Sector N de las NNSS») requieren mapeo heurístico al código SITCM.
  - Tablón/PDFs sin georreferencia directa.
  - Sede requiere `insecure_ssl: true` (cadena CA no verificada en entorno agente).

## Limitaciones generales

- Sede `lossantosdelahumosa.sedelectronica.es`: certificado SSL con cadena incompleta → `insecure_ssl`.
- Tablón muestra solo anuncios recientes (~10 filas).
- Transparencia y dossier dependen de Wicket AJAX (no scrapeados).
- Sin visor ArcGIS municipal; geometría solo vía SITCM regional.
- No hay sección web dedicada a urbanismo/PGOU (a diferencia de municipios vecinos).

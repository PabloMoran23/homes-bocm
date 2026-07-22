# Loeches — investigación portal ayuntamiento

Municipio: **Loeches** (`loeches`) — Comunidad de Madrid, boletín BOCM (17 entradas).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web corporativa | https://loeches.es | WordPress 6.x + Yoast SEO |
| Urbanismo (área) | https://loeches.es/urbanismo/ | Página informativa (sin listado expedientes) |
| PGOU | https://loeches.es/plan-general-de-ordenacion-urbana/ | PDFs: PLANOS, MEMORIA-PRELIMINAR, TRIPTICO |
| Noticias urbanismo | https://loeches.es/wp-json/wp/v2/posts?categories=34 | WP REST API (5 posts) |
| Sede electrónica | https://loeches.sedelectronica.es | espublico gestiona (eHome) |
| Tablón anuncios | https://loeches.sedelectronica.es/board | Tabla HTML con preview-document PDF |
| Transparencia | https://loeches.sedelectronica.es/transparency/ | Portal Wicket (17 docs urbanismo) |
| Consulta expedientes | https://loeches.sedelectronica.es/expedientes | Requiere Cl@ve (no listado público) |

## Cómo se listan expedientes / proyectos

1. **WordPress REST** — categoría `urbanismo` (id 34): noticias de PGOU, sector industrial calle Ronda, etc.
2. **PGOU page** — enlaces directos a PDFs en `/wp-content/uploads/`.
3. **Tablón sede** — tabla con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Solo ~10 anuncios visibles (sin paginación accesible sin JS Wicket). Categorías relevantes: `Urbanismo`, `Licencias Urbanísticas`, `Licencias de Actividad`.
4. **Transparencia sede** — sección "6. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (17)" con navegación Wicket/AJAX; no scrapeable de forma determinista sin sesión JS.

## Cómo se publican licencias

- **Tablón sede** (`/board`): publica licencias urbanísticas y de actividad con PDF en `preview-document/{uuid}`.
- **No hay dataset abierto** de concesiones históricas ni listado CSV.
- Trámites informativos en sede (`/dossier`, `/citizen-service/...`) cargan vía Wicket; timeout en CI.
- Páginas informativas de trámites incluidas como filas de referencia (patrón Humanes/Móstoles).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='LOECHES'`
  - 8 ámbitos: S-1 CABEZO GORDO, S-2 PANCHO CHICO, S-3 CAMINO PERALTA, S-4 VALDEPOZUELO, S-5 EL CRUCERO, S-6 LOS PRADOS, U-1, U-2
- **Estrategia:** query WFS por código ámbito (S-N, U-N) o matching fuzzy por nombre de sector en título del expediente/noticia.
- **Limitaciones:**
  - No hay visor urbanístico propio del ayuntamiento ni enlace expediente→polígono.
  - SITCM cubre ámbitos de planeamiento, no parcelas de licencias individuales.
  - Tablón/PDFs sin georreferencia directa.
  - Sede requiere `insecure_ssl: true` (cadena Sectigo no verificada en entorno agente).

## Limitaciones generales

- Sede `loeches.sedelectronica.es`: certificado SSL con cadena incompleta → `insecure_ssl`.
- Tablón muestra solo anuncios recientes (~10 filas).
- Transparencia y dossier dependen de Wicket AJAX (no scrapeados).
- Sin visor ArcGIS municipal; geometría solo vía SITCM regional.

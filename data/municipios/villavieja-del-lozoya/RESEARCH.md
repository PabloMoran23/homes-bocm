# Villavieja del Lozoya — investigación portal ayuntamiento

**Municipio:** Villavieja del Lozoya (Comunidad de Madrid)  
**Fecha:** 2026-07-23  
**BOCM regional (referencia):** 15 avisos

## Resumen

Villavieja del Lozoya publica planeamiento y documentación urbanística en su **web municipal WordPress**
(`villaviejadellozoya.es`) y gestiona trámites en la **sede electrónica espublico gestiona**
(`villaviejadellozoya.sedelectronica.es`). Los ámbitos de planeamiento municipal están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo | `https://villaviejadellozoya.es/urbanismo/` | WordPress HTML | Expediente modificación NNSS (enlace BOCM) |
| Normas Subsidiarias | `https://villaviejadellozoya.es/urbanismo/normas-subsidiarias/` | PDFs WP | Acuerdo, catálogo, memoria, normas, planos (2024) |
| Avance PGOU | `https://villaviejadellozoya.es/avance-del-plan-general-de-villavieja-del-lozoya/` | PDFs WP | Documentación avance PGOU (2018) |
| Urbanizaciones | `https://villaviejadellozoya.es/urbanizaciones/` | WP acordeones + PDFs | Las Cabezas, La Cañada, El Molinillo-Los Llanos, Tercio de la Laguna, La Solanilla |
| Licencias obra | `https://villaviejadellozoya.es/licencias-de-obra-mayor-y-menor/` | WP informativo | Formularios y requisitos |
| Tablón sede | `https://villaviejadellozoya.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios (vacío jul 2026) |
| Transparencia sede | `https://villaviejadellozoya.sedelectronica.es/transparency/` | Wicket | Portal transparencia |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 10 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VILLAVIEJA DEL LOZOYA'` |

## Cómo se listan expedientes

- **Planeamiento:** PDFs enlazados desde páginas WP (normas subsidiarias, avance PGOU, urbanizaciones).
  Acordeones Visual Composer (`vc_tta-panel`) agrupan documentos por urbanización.
- **Tablón sede:** Tabla HTML espublico con columnas Documento/Expediente/Procedimiento/Categoría/Descripción/Fecha.
  En julio 2026 sin filas publicadas.
- **No hay** visor urbanístico propio ni API JSON de expedientes.

## Licencias

- Páginas informativas de trámites (obra mayor/menor, primera ocupación) en WordPress.
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón sede cuando se publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VILLAVIEJA DEL LOZOYA'` (`srsName=EPSG:4326`)
  - Enlace al visor SIT CM en página NNSS (`comunidad.madrid/servicios/urbanismo-medio-ambiente/sistema-informacion-territorial-visor-sit`)
  - 10 ámbitos: UE-A-1/2/3, UE-B, ACTUACIÓN AISLADA 1/2, TERCIO DE LA LAGUNA, LA CAÑADA, LAS CABEZAS, EL MOLINILLO
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos WP cuando el título contiene código UE o nombre de urbanización SIT.
- **Limitaciones:** PDFs sin georreferenciación directa; tablón vacío; transparencia Wicket no automatizable en CI; sede `/dossier` con timeouts intermitentes.

## Limitaciones

- Tablón sede sin anuncios activos (tabla vacía).
- Sede `/dossier` puede responder lentamente o con timeout.
- Licencias solo como páginas de trámite, sin concesiones publicadas.
- PDFs de planeamiento sin enlace a expediente GIS individual.

## Estrategia adapter

1. Crawl páginas WP semilla (urbanismo, NNSS, PGOU, urbanizaciones).
2. Parsear acordeones y PDFs con título contextual.
3. Semillas de ámbitos SIT WFS (10 figuras) con `geom_geojson`.
4. Tablón sede (cuando tenga filas) + páginas informativas de licencias.
5. IDs: `villavieja-del-lozoya-{lic|proy}-{sha256[:14]}`.

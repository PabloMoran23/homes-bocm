# Torrejón de la Calzada — investigación portal ayuntamiento

**Municipio:** Torrejón de la Calzada (Comunidad de Madrid)  
**Slug:** `torrejon-de-la-calzada`  
**Fecha:** 2026-08-11  
**BOCM regional (referencia):** 5 avisos

## Resumen

Torrejón de la Calzada publica anuncios administrativos en la **sede electrónica espublico gestiona**
(`aytotorrejoncalzada.sedelectronica.es`) y dispone de web corporativa **WordPress**
(`www.aytotorrejoncalzada.es`). No hay visor urbanístico municipal propio; el planeamiento
vigente está en el **SIT de la Comunidad de Madrid** (WFS público). Las **intervenciones urbanas**
en curso se publican en un mapa **uMap** (OpenStreetMap) con 44 puntos georreferenciados.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://www.aytotorrejoncalzada.es` | WordPress | Noticias, trámites, ordenanzas, mapa intervenciones |
| Tablón de anuncios (sede) | `https://aytotorrejoncalzada.sedelectronica.es/board` | HTML tabla Wicket | Edictos, exposiciones públicas, convocatorias |
| Portal transparencia | `https://aytotorrejoncalzada.sedelectronica.es/transparency/` | Wicket AJAX | Sección 7: Urbanismo (48 docs) — requiere sesión |
| Consulta expedientes | `https://aytotorrejoncalzada.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación |
| Trámites licencias | `https://www.aytotorrejoncalzada.es/tramites/` | HTML estático | Modelos 01-10 (licencia, DR, comunicación previa…) |
| Ordenanza licencias | PDF en `/wp-content/uploads/2024/01/` | PDF | Régimen de licencia y declaración responsable |
| Mapa intervenciones | `https://umap.openstreetmap.fr/es/map/mapa-interactivo-de-intervenciones-urbanas_1197502` | uMap GeoJSON | 44 actuaciones en espacio público (puntos WGS84) |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 25 ámbitos PGOU (S-*, UE-*, API-*) — código municipio 149 |

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (ago 2026):

- Exposición pública cuenta general 2025 (BOCM 28/07/2026)
- Anuncios sancionadores tráfico (BOE)
- Convocatorias JLS, decretos administrativos

No hay anuncios de licencias urbanísticas recientes en la primera página; el tablón es la vía
habitual cuando se publiquen concesiones (patrón espublico vecino).

Paginación: botón Wicket AJAX «cargar más» (tokens de sesión; no implementado en adapter).

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Trámites y modelos normalizados en `/tramites/` (licencia, DR, comunicación previa, etc.).
- Ordenanza reguladora del régimen de licencia (PDF 2024) en ordenanzas municipales.
- Consulta de expedientes en sede requiere Cl@ve.

## Mapa intervenciones urbanas (uMap)

- **URL:** `https://umap.openstreetmap.fr/es/map/mapa-interactivo-de-intervenciones-urbanas_1197502`
- **Datalayer JSON:** `/es/datalayer/1197502/2eef579e-2d23-4282-ab26-704a83385e4e/`
- **Contenido:** 44 puntos con nombre de actuación (asfaltados, aparcamientos, ecoparque, etc.)
- **Geometría:** `Point` en EPSG:4326 (lon, lat)
- Tours 360° en Kuula embebidos en descripción (no scrapeados)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
    — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='TORREJÓN DE LA CALZADA'`
    (código SIT `149`). 25 ámbitos únicos: S-1…S-9, S-T1…S-T7, S-I*, UE-1/2, API-5/6.
  - Visor SIT: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=149`
  - uMap intervenciones: 44 puntos GeoJSON públicos (obra pública, no planeamiento)
- **Estrategia:**
  1. Ingestar ámbitos SIT como proyectos con polígono WFS.
  2. Ingestar intervenciones uMap como proyectos con punto.
  3. Enriquecer anuncios del tablón si el título menciona código de ámbito (UE-*, S-*, API-*).
- **Limitaciones:** Tablón sin georreferenciación por expediente; transparencia tras AJAX Wicket;
  expedientes tras login; uMap solo cubre obras en espacio público (no licencias privadas).

## Limitaciones

- Tablón muestra ~10 anuncios recientes; histórico requiere paginación Wicket.
- Portal transparencia urbanismo (48 docs) no scrapeable sin tokens de sesión.
- WordPress tablón (`/tablon-de-anuncios/`) sin listado estructurado de urbanismo.
- Sin listado público de licencias concedidas con dirección/coordenadas.

## Estrategia adapter

1. Scrape tabla tablón `/board` (parser `data-label`).
2. Páginas informativas: tablón, consulta expedientes, trámites WP, ordenanza licencias.
3. Ámbitos PGOU desde WFS SIT (25 filas con polígono).
4. Intervenciones urbanas desde uMap datalayer (44 filas con punto).
5. Geometría WFS adicional cuando el título del tablón contenga código de ámbito.
6. IDs estables: `torrejon-de-la-calzada-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `torrejon_de_velasco.py`, `humanes_de_madrid.py`
- WFS SIT + ámbitos: `san_martin_de_valdeiglesias.py`, `torrejon_de_velasco.py`

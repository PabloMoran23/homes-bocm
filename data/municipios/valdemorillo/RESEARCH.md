# Valdemorillo — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `valdemorillo` |
| Web oficial | https://aytovaldemorillo.com |
| Sede electrónica | https://aytovaldemorillo.sedelectronica.es |
| CMS web | WordPress + Elementor (OceanWP) |
| Sede | eHome / esPublic (Maggioli) |
| BOCM | 14 entradas históricas |

**Nota:** `www.valdemorillo.es` no resuelve. La web operativa es `aytovaldemorillo.com`.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Urbanismo | https://aytovaldemorillo.com/urbanismo/ |
| Urbanizaciones | https://aytovaldemorillo.com/urbanizaciones-urbanismo-y-movilidad/ |
| WP REST urbanismo | https://aytovaldemorillo.com/wp-json/wp/v2/pages/31606 |
| Tablón sede | https://aytovaldemorillo.sedelectronica.es/board/ |
| Transparencia PGOU avance | https://aytovaldemorillo.sedelectronica.es/transparency/4776aa0e-ebd0-438b-b391-6f8671ede0b2/ |
| esPublico (alias) | https://valdemorillo.espublico.es (landing genérica, sin tablón operativo) |

## Proyectos / planeamiento

### Web municipal (WordPress)

La página `/urbanismo/` (Elementor + acordeón EAEL) publica:

- **Normas subsidiarias (NNSS):** PDFs en `/wp-content/uploads/2022/02/` (`nurbanisticas_valdemorillo.pdf`, `indice_nurbanisticas.pdf`, `memoria.pdf`, `planos-*.pdf`, `acuerdo.pdf`, `catalogo.pdf`).
- **Avance PGOU (2026):** bando PDF `20260522_Publicacion_Bando_BANDO-INFORMACION-PUBLICA-AVANCE-PGOU.pdf`.
- **Formularios:** enlaces al catálogo de trámites de la sede (`/catalog/t/{uuid}`).

Listado vía HTML embebido en REST API (`wp-json/wp/v2/pages/31606`) y búsqueda en `wp-json/wp/v2/media`.

### Sede electrónica

- Tablón `/board/` y transparencia devuelven **HTTP 503** («En mantenimiento») desde jul-2026.
- Cuando esté activa, el tablón eHome lista anuncios con columnas Documento / Expediente / Procedimiento / Categoría / Descripción / Fecha y enlaces `preview-document/{uuid}`.

### SITCM (Comunidad de Madrid)

WFS público con **25 ámbitos** del municipio (`UA-*`, `SAU-*`, nombres descriptivos como «UA CERRO ALARCÓN», «UA EL PARAÍSO»).

## Licencias de obra

- **Catálogo sede** (enlaces en web urbanismo): declaraciones responsables, solicitudes de licencia mayor/menor, alineación, segregación, etc. (`/catalog/t/*`).
- **Tablón:** concesiones publicadas cuando la sede está operativa (actualmente inaccesible).
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VALDEMORILLO'`
  - Campo nombre: `DS_NOMB_AMB` (códigos UA/SAU en el título)
- **Estrategia:** ingestar cada ámbito WFS como proyecto con `geom_geojson`; enriquecer PDFs/bandos si el título cita código UA/SAU.
- **Limitaciones:**
  - Sede y tablón en mantenimiento (503) — sin expedientes recientes del tablón.
  - No hay visor ArcGIS propio del ayuntamiento enlazado al expediente.
  - PDFs de NNSS/PGOU no traen geometría embebida; solo polígonos vía SITCM cuando hay match de ámbito.

## Limitaciones generales

- Dominio `valdemorillo.sedelectronica.es` (sin prefijo `ayto`) muestra selector genérico «Sede Indeterminada».
- `valdemorillo.espublico.es/board` redirige a landing comercial esPublico, no al tablón municipal.
- SSL y certificados de la sede correcta OK cuando no está en mantenimiento.

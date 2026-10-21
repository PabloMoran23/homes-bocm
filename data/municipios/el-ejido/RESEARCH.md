# El Ejido — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://elejido.es/ (WordPress) |
| Sede / Oficina Virtual | https://sede.elejido.es/oficinavirtual/ |
| Tablón de anuncios | https://sede.elejido.es/oficinavirtual/tablonanuncios/index.php |
| Listado AJAX tablón | `tablonanuncios/listadoanuncios.php` (`pagina`, `numero_filas`, `area`) |
| Detalle anuncio | `tablonanuncios/detalleanuncio.php?id=` |
| Catálogo trámites | https://sede.elejido.es/oficinavirtual/catalogopublico/ |
| Portal Urbanismo | https://urbanismo.elejido.es/ (WordPress, secciones planeamiento) |
| Callejero | https://elejido.es/callejero/ (Leaflet + GeoJSON estático) |
| SITUA PGOU (Junta) | `planeamientoGeneralCompartir.jsf?codigosMunicipios=04051` |

## Tablón de anuncios

- CMS propio de la Oficina Virtual (PHP + Bootstrap + jQuery).
- El listado se carga vía GET a `listadoanuncios.php` (misma API que usa `ajax_tablonAnuncios.js`).
- Filtro por área: `area=2` (Urbanismo), `area=16` (Desarrollo Urbanístico de El Ejido).
- Paginación ~16 páginas × 50 filas en Urbanismo (oct 2026).
- Cada fila enlaza a `detalleanuncio.php?id=` con PDFs en `transparencia.elejido.es/.../TablonEdictos/urbanismo/`.
- Tipos habituales: información pública, trámite de audiencia, licencias, calificación ambiental (con nº expediente en título, p. ej. `EXPTE. 427/2026`).

## Licencias

- No hay listado público de concesiones con coordenadas.
- Concesiones y anuncios de obra aparecen en el **tablón** (área Urbanismo).
- Trámites telemáticos en catálogo (`area_id=4` — Actividades/Licencias Urbanismo): licencia obra mayor/menor, comunicaciones previas, declaraciones responsables (códigos D220/D230).
- El adapter incluye páginas informativas del catálogo y tablón (patrón Pozuelo/Lucena).

## Planeamiento / proyectos

- Anuncios de información pública y calificación ambiental en tablón.
- Instrumentos y modificaciones en https://urbanismo.elejido.es/planeamiento/ (PDFs históricos).
- Consulta autonómica PGOU vía SITUA (municipio 04051).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Callejero municipal (`data/calles.geojson`, `numeros.geojson`): geometría de vías y portales, **sin** campo de expediente urbanístico.
  - urbanismo.elejido.es: contenido editorial/PDF, sin MapServer/ArcGIS/WFS público.
  - Tablón: solo PDFs en transparencia, sin georreferencia en metadatos HTML.
  - SITUA/VITUA Junta: planeamiento a escala municipal, no enlazable por código de expediente del tablón municipal.
- **Estrategia:** geocode del orquestador (centroide municipio + jitter).
- **Limitaciones:** no hay visor urbanístico municipal con query por expediente; callejero no sirve para polígonos de proyecto.

## Limitaciones

- Backfill del tablón requiere ~16–32 peticiones (áreas 2 y 16) con `request_delay_s`.
- Catálogo de procedimientos carga listados en panel JS; el adapter usa URLs de área y semillas estáticas.
- Sin boletín regional asociado en cola (`bocm_count: 0`).

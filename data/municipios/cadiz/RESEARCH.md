# Cádiz — investigación portal ayuntamiento

Municipio: **Cádiz** (`cadiz`) — Andalucía, provincia Cádiz. Boletín: BOJA.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal institucional | https://institucional.cadiz.es |
| Delegación Urbanismo | https://institucional.cadiz.es/area/Urbanismo/57 |
| Tablón de anuncios (listado) | https://institucional.cadiz.es/area/Tabl%C3%B3n-de-anuncios-Ayto.-C%C3%A1diz/646 |
| Tablón urbanismo (ítems) | https://institucional.cadiz.es/urbanismo-{N} (N≈1..398) |
| PGOU | https://institucional.cadiz.es/area/Plan-General-de-Ordenaci%C3%B3n-Urban%C3%ADstica-(PGOU)/677 |
| Modificaciones PGOU en trámite | https://institucional.cadiz.es/area/Modificaciones-del-PGOU-(en-tr%C3%A1mite)/2443 |
| Modificación PGOU Hospedaje | https://institucional.cadiz.es/area/Modificaci%C3%B3n%20PGOU%20%22Hospedaje%20y%20Equipamiento%22/2446 |
| Convenios urbanísticos | https://institucional.cadiz.es/area/Convenios-urban%C3%ADsticos/806 |
| Trámites / solicitudes | https://institucional.cadiz.es/area/Solicitudes/595 |
| Sede electrónica | https://portaldelcontribuyente.cadiz.es/portalCiudadano |
| Datos abiertos | http://datos.cadiz.es/ (sin capas urbanísticas por expediente) |

## CMS y estructura

- **CMS:** Drupal 7 (`corporate` theme), sede propia en `portaldelcontribuyente.cadiz.es`.
- **Expedientes / planeamiento:** publicados en el **tablón virtual** con alias URL `urbanismo-{id}`.
  Cada ficha HTML incluye: Tablón, Resumen, Fecha de publicación, Descripción y PDF(s) en
  `/sites/default/files/tablon/archivos/`.
- **Listado reciente:** vista Drupal en `/area/Tablón-de-anuncios-Ayto.-Cádiz/646` (≈9 filas, sin paginador).
- **PGOU:** árbol de PDFs estáticos bajo `/media/docs/PGOU_2011/` y subáreas de modificaciones.
- **Licencias:** no hay dataset histórico de concesiones; solo trámites informativos (formularios Drupal)
  y edictos puntuales en tablón (p. ej. sección Comercio con licencias de apertura).

## Licencias

- Trámites: `/area/Solicitudes/595`, `/area/Licencias-de-obras/410`, subsecciones de apertura/actividad.
- Concesiones publicadas: aparecen como PDF en tablón (filtrar por palabras clave licencia/calificación ambiental).
- Sede `portaldelcontribuyente.cadiz.es`: catálogo de trámites sin API de concesiones históricas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Portal municipal: sin visor urbanístico ni MapServer/FeatureServer por expediente.
  - Datos abiertos Cádiz (`datos.cadiz.es`): censos, deporte, etc.; sin capa de expedientes/ámbitos.
  - **GeoCádiz** (Diputación): https://www.dipucadiz.es/idecadiz/visor/ — cartografía provincial
    (PGOU, parcelario Catastro) sin campo de enlace a expediente municipal.
- **Estrategia:** el orquestador aplicará centroide municipio + jitter (`centroid: [36.5297, -6.2924]`).
- **Limitaciones:** tablón = PDF sin georreferencia; consulta expediente urbanismo requiere trámite presencial/sede.

## Limitaciones

- Escaneo secuencial `urbanismo-N` (~400 peticiones, ~2 min con delay 0.35s).
- Listado tablón sin paginación pública (solo anuncios recientes no urbanísticos).
- Sin geometría por expediente; `with_geometry` esperado = 0.

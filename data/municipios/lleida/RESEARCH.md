# Lleida — investigación portal ayuntamiento

## Fuentes principales

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web urbanismo (Plone) | https://urbanisme.paeria.cat | POUM, convenios, exposición pública, noticias (RSS) |
| Registro planeamiento (seu) | https://seu.paeria.cat/urbanismeCategoriaPublic/ | Listado paginado por categoría (HTML) |
| Redirect desde Plone | `registre-de-planejament-urbanistic-de-lleida` → seu cat. 7 | |
| Sede / trámites | https://tramits.paeria.cat | Catálogo trámites (licencias urbanísticas informativas) |
| Portal municipal | https://www.paeria.cat | Sección urbanismo, planos, geoportal |

### Categorías registre públic (seu.paeria.cat)

- `7` — Planejament general
- `154` — Planejament derivat
- `8` — Convenis urbanístics
- `328` — Gestió Urbanística
- `337` — Ordenació detallada

Cada fila incluye fecha, enlace `/registrePublic/registrePublicacio/{id}`, número de expediente, instrumento y tema (título).

### Licencias

No hay listado público de licencias concedidas con dirección/coords. El tablón de anuncios de la seu enlaza a trámites; el adapter incluye páginas informativas de licencias/comunicaciones previas en `tramits.paeria.cat` y filas del registre cuyo tema menciona licencia.

### Semillas Plone

- Exposición pública / incidencia ambiental
- Convenios urbanísticos (PDF)
- POUM Lleida 2025
- Enlace e-tauler (informativo)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** [Geoportal SIG Lleida](https://www.paeria.cat/ca/ciutat/planols/geoportal-sig-lleida) → ArcGIS Hub (`planol-de-la-ciutat-paeria.hub.arcgis.com`) con cartografía municipal y planeamiento general; no expone consulta por código de expediente del registre seu.
- **Estrategia:** El orquestador usará centroide municipal + jitter (`coord_source` geocode).
- **Limitaciones:** Registro de publicaciones es HTML/PDF sin enlace GIS por expediente; visor OVAC (`ovac.paeria.cat`) no aporta API pública enlazable en esta investigación.

## Limitaciones técnicas

- Paginación del registre (10 ítems/página); adapter limita páginas por categoría.
- Contenido mayoritariamente en catalán.
- RSS de urbanisme mezcla noticias de servicios urbanos con planeamiento; se filtra por palabras clave.

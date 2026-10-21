# Barakaldo — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.barakaldo.eus |
| Planeamiento / información pública | https://www.barakaldo.eus/portal/es/web/planeamiento-y-gestion/informacion-publica |
| Sede electrónica (SIBAE) | https://www.barakaldo.eus/OficinaVirtualBarakaldo/ |
| Tablón anuncios y edictos | https://www.barakaldo.eus/OficinaVirtualBarakaldo/buscarFiltrosBusquedaTablonAnuncios.do |
| Licencias de obras (info Liferay) | https://www.barakaldo.eus/portal/web/licencias-de-obras/licencias-de-obras |
| Trámites licencias (SIBAE, codMenu=3) | https://www.barakaldo.eus/OficinaVirtualBarakaldo/inicio.do?codMenu=3 |

## Cómo se listan expedientes / proyectos

1. **Tablón SIBAE (desde oct. 2020)** — La página de información pública remite al tablón electrónico. La búsqueda es **POST AJAX** a `buscarTablonAnuncios.do` (respuesta JSON con campo `html`). Filtro `codTemaAnuncio=24` (Urbanismo). Cada fila enlaza a `detalleAnuncio.do?codAnuncio=<id>`.
2. **Noticias Liferay** — El portlet `listadocontenidos` en la misma URL de información pública lista noticias históricas de planeamiento (`plantilla_noticia_listado`, fechas + enlaces con `articleId`).

No hay API JSON de expedientes ni visor de consulta por código de expediente enlazado al tablón.

## Licencias de obra

- El tablón con tema **Licencias urbanísticas** (`codTemaAnuncio=10`) devuelve **0** anuncios en la fecha de investigación.
- Las concesiones no aparecen en listado público; solo **páginas de trámite** en la sede (obra menor/mayor, ascensor, etc.) y sección Liferay de licencias.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Mapa web municipal (`/portal/web/barakaldo/mapa-web`) — enlaces externos (gestiones inmigración, teatro, etc.), sin capas de planeamiento ni enlace a expediente.
  - OpenData Bizkaia — dataset agregado de planeamiento (CSV/JSON estadístico), sin geometría por expediente ni campo de enlace.
  - Tablón y noticias — solo HTML/PDF en detalle, sin coordenadas ni `objectId` GIS.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** sin visor ArcGIS/WFS municipal consultable por expediente; PGOU en documentos PDF en Liferay.

## Limitaciones técnicas

- Sesiones `jsessionid` en URLs Liferay (se normalizan al guardar).
- Tablón: paginación vía `paginaActual` / `registrosPagina` (máx. ~50 por página).
- Detalle de anuncio sin adjuntos PDF sistemáticos en la muestra revisada.

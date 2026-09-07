# Anchuelo — investigación portal ayuntamiento

**Slug cola:** `anchuelo-y-villalbilla`  
**Municipio portal:** Anchuelo (Comunidad de Madrid, provincia Madrid, INE 28009)  
**Nota cola:** El slug combina erróneamente «Anchuelo» y «Villalbilla» (artefacto BOCM). Villalbilla tiene pipeline propio en `villalbilla`. Esta PR cubre **solo el portal de Anchuelo**.

## URLs base y páginas semilla

| Recurso | URL | CMS / tecnología |
|---------|-----|------------------|
| Web corporativa | https://aytoanchuelo.com | WordPress 6.8 (Hestia + ThemeIsle blocks) |
| REST API | https://aytoanchuelo.com/index.php/wp-json/wp/v2/ | WP REST (requiere `index.php` en path) |
| Avance PGOU | https://aytoanchuelo.com/index.php/avance-pgou/ | Página estática WP |
| Normativas | https://aytoanchuelo.com/index.php/normativas-municipales/ | Secciones vacías (sin PDFs enlazados) |
| Sede electrónica | https://sedeanchuelo.eadministracion.es | Maggioli eAdmin — **404** en raíz |
| Transparencia | https://transparenciaanchuelo.eadministracion.es | Maggioli — **portal no disponible** |
| Evaluación ambiental avance PGOU (CM) | http://www.comunidad.madrid/transparencia/normativa/consultas-procedimiento-evaluacion-ambiental-estrategica-avance-plan-general-ordenacion | Enlace desde avance-pgou |

## Proyectos / expedientes urbanísticos

- **Listado:** noticias WP (~354 posts) vía REST API; no hay visor de expedientes ni tablón scrapeable.
- **Contenido relevante encontrado:**
  - Revisión PGOU: periodo IP avance (2021-03-12), aprobación inicial revisión (2021-11-03)
  - Página «Avance PGOU» con enlace a consulta ambiental estratégica CM
  - Información pública instalaciones (planta fotovoltaica Anchuelo, 2021–2022)
  - Anuncios Delegación Gobierno Madrid (autorización administrativa previa, declaración utilidad pública)
  - Bandos desbroce parcelas urbanas/rústicas (ordenanza incendios — suelo urbano)
- **Formato:** HTML WP + PDFs adjuntos en `/wp-content/uploads/` (cuando existen)
- **Paginación REST:** `per_page=100`, hasta ~4 páginas

## Licencias de obra

- **No hay listado público** de licencias concedidas (ni tablón ni dataset).
- Trámites presenciales / sede eAdmin (inaccesible desde agente).
- El adapter incluye páginas informativas de referencia (sede, transparencia, ciudadanos) al estilo Pozuelo/Madarcos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCM WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='ANCHUELO'`
  - 9 ámbitos UA-1 … UA-9 (unidades de actuación PGOU)
  - Visor CM: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** `resolve_ambito_geometry()` por tokens UA-X en título; enriquecimiento en adapter vía `_fetch_geometry()`
- **Limitaciones:**
  - Sin visor municipal de expedientes ni geometría por licencia
  - Sede/transparencia eAdmin no operativas (404 / portal no disponible)
  - Normativas municipales sin PDFs enlazados en web
  - Proyectos genéricos (PGOU revisión) sin código UA → sin polígono automático

## Limitaciones generales

- Sede `sedeanchuelo.eadministracion.es` devuelve 404; transparencia deshabilitada
- Sin certificado problemático (SSL OK en aytoanchuelo.com)
- WP REST requiere path `/index.php/wp-json/` (no `/wp-json/` directo)

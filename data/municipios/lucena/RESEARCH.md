# Lucena — investigación portal ayuntamiento

Municipio: **Lucena** (`lucena`)  
Provincia: Córdoba · CCAA: Andalucía

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Portal municipal | https://lucena.es | WordPress Divi + REST API |
| Urbanismo (transparencia) | https://lucena.es/medio-ambiente-urbanismo-y-obras-publicas/ | Enlaces a PGOU y transparencia |
| Delegación urbanismo | https://lucena.es/delegacion-de-urbanismo-y-ordenacion-del-territorio/ | Contacto; sin listado de expedientes |
| Normativa municipal | https://lucena.es/normativa-municipal/ | PDFs tasas/ordenanzas urbanísticas |
| Transparencia PGOU | https://transparencia.lucena.es/publicidad_activa/plan-general-de-ordenacion-urbana-pgou-y-los-mapas-y-planos-que-lo-detallan/ | Remite a visor histórico |
| Modificaciones PGOU | https://transparencia.lucena.es/publicidad_activa/modificaciones-aprobadas-del-pgou-y-planes-parciales-aprobados/ | Publicidad activa |
| Sede electrónica | https://sede.eprinsa.es/lucena | Plataforma Diputación Córdoba (eprinsa) |
| Tablón de edictos | https://sede.eprinsa.es/lucena/tablon-de-edictos | SPA Ember; sin API REST pública |
| Trámites | https://sede.eprinsa.es/lucena/tramites | Catálogo procedimientos (licencias vía sede) |
| Expedientes | https://sede.eprinsa.es/lucena/expedientes | Requiere Cl@ve/certificado |
| Open data | https://lucena-opendata.e-admin.es/ | CKAN (callejero, adjudicaciones); sin capa PGOU |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta planeamiento regional |

## Proyectos / planeamiento

- **Noticias:** `wp-json/wp/v2/posts?search=urbanismo|planeamiento|plan especial` — actuaciones (Plan Especial Campo de Aras, consultas, licencias noticiadas).
- **Normativa:** PDFs en `/wp-content/uploads/` (tasas urbanísticas, ICIO, suelo).
- **PGOU:** La web municipal enlaza `http://urbanismo.aytolucena.es/` (**no resuelve DNS** desde entorno cloud, 2026-10). Transparencia mantiene fichas de publicidad activa sin PDFs embebidos en HTML estático.
- **No hay** listado abierto de expedientes urbanísticos ni RSS de información pública estructurado.

## Licencias

- Concesiones y edictos en **tablón eprinsa** (contenido cargado por JavaScript; no scrape determinista sin token de sesión).
- Trámites de licencia en sede; modelos/tasas en normativa municipal (PDF).
- Noticias WP ocasionales («licencia proyecto…»).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `urbanismo.aytolucena.es` — caído / sin DNS
  - Open data Lucena — callejero (CKAN), sin polígonos de expedientes
  - Diputación Córdoba geoportal (WMS/WMTS citado en transparencia) — cartografía provincial, sin join a expediente municipal
  - SITUA — metadatos de planeamiento, no geometría por licencia/expediente del ayto.
- **Estrategia:** centroide municipal en manifest (`centroid`) + jitter en orquestador.
- **Limitaciones:** tablón SPA; PGOU en visor legacy inaccesible; licencias sin coordenadas públicas.

## Limitaciones generales

- Sede eprinsa compartida con otros municipios de la Diputación de Córdoba (mismo patrón que Fernán Núñez, Benamejí).
- Sin `boletin_source_id` en cola (0 entradas BOCM); referencia regional BOJA por CCAA.

# Villaquilambre — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.villaquilambre.es |
| Urbanismo (índice) | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/ |
| Edictos | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/edictos/ |
| Proyectos | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/proyectos/ |
| PGOU | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/plan-general-de-ordenacion-urbana/ |
| Estudio detalle SUR-01 | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/estudio-detalle-sur-01/ |
| Licencias (formularios) | https://www.villaquilambre.es/atencion-al-ciudadano/urbanismo/licencias/ |
| Sede electrónica (espublico) | https://villaquilambre.sedelectronica.es |
| Tablón de anuncios | https://villaquilambre.sedelectronica.es/board |
| PLAI JCyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=241 |
| PLAI JCyL (archivo) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=241 |
| Transparencia | https://villaquilambre.transparencialocal.gob.es |

## CMS y formato de datos

- **Web:** WordPress (LiteSpeed, Rank Math, FileBird). REST API en `/wp-json/wp/v2/`.
- **Sede:** espublico gestiona (Wicket/YUI). Tablón en `/board` con tabla HTML (`preview-document` por fila).
- **Proyectos/edictos:** páginas WP estáticas con enlaces directos a PDF en `/wp-content/uploads/` y `/wordpress/wp-content/uploads/`.
- **Licencias:** no hay listado de concesiones; solo formularios PDF de solicitud en la sección urbanismo.
- **Planeamiento autonómico:** JCyL PLAI (código municipio 241, provincia León 24).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores` (53 polígonos), `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (1)
  - Filtro: `CQL_FILTER=n_mun='Villaquilambre'`
  - Campos: `n_num_sect` (p. ej. `SU-NC-07`, `SUR-29`), `c_id_sect`, `n_sector`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector (`SUR-XX`, `SU-NC-XX`, `UA-X`) en títulos de edictos/PDF/tablon.
- **Limitaciones:** no hay visor municipal propio ni enlace expediente→geometría; geometría es a nivel de sector PGOU, no por expediente individual. Sin coords en tablón ni PDFs.

## Limitaciones generales

- Tablón sede muestra solo ~10 anuncios recientes (paginación); urbanismo aparece esporádicamente (p. ej. actuaciones SUR-29).
- `/urbanismo/planeamiento-urbanistico/` devuelve WAF «Request Rejected» desde algunos entornos.
- Licencias: solo trámites informativos, sin registro público de concesiones.

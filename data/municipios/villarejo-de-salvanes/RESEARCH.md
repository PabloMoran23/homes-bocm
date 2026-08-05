# Villarejo de Salvanés — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.villarejodesalvanes.es |
| Urbanismo y vivienda | https://www.villarejodesalvanes.es/areas-municipales/urbanismo-y-vivienda/ |
| Trámites sin certificado (formularios urbanismo) | https://www.villarejodesalvanes.es/tramites-administrativos/tramites-sin-certificado-digital/ |
| Nuevos trámites urbanismo | https://www.villarejodesalvanes.es/nuevos-tramites-urbanismo/ |
| Sede electrónica | https://villarejodesalvanes.sedelectronica.es |
| WP REST API | https://www.villarejodesalvanes.es/wp-json/wp/v2 |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress (tema citygovt + Elementor).
- **Planeamiento:** PDFs estáticos enlazados en la página de urbanismo (NNSS 2002, anexos, planos de ordenación OR-01…OR-05, convenio Las Huertas, proyecto de reparcelación 2017 en múltiples partes).
- **No hay** listado dinámico de expedientes en información pública ni visor urbanístico municipal.
- **Sede electrónica** (plataforma espublico): URLs `/board`, `/transparency` no responden desde el entorno del scraper (sin tablón accesible vía HTTP simple).

## Licencias de obra

- **No hay** tablón público de concesiones de licencias.
- Formularios descargables: solicitud licencia urbanística, declaración responsable, comunicación previa (`/wp-content/uploads/2023/08/*.pdf`).
- Trámites telemáticos vía sede (presentación, no listado de concesiones).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `sitcm:VPLA_V_AMBITO` — 58 ámbitos para `DS_MUNICIPIO='VILLAREJO DE SALVANÉS'` (SAU-1…SAU-24, UE-13…UE-24, etc.).
  - URL: `https://idem.comunidad.madrid/geoserver3/ows` con `CQL_FILTER=DS_MUNICIPIO ILIKE '%SALVAN%'` y `srsName=EPSG:4326`.
- **Estrategia:** Enriquecer proyectos cuyo título contiene código de ámbito (UE-*, SAU-*) vía `resolve_ambito_geometry` / WFS. PDFs de planeamiento sin código no tienen polígono enlazable.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni GeoJSON en datos abiertos del ayuntamiento.
  - Planos NNSS/reparcelación solo en PDF/DWG sin API.
  - Sede sin tablón scrapeable → licencias sin coords de obra.

## Limitaciones generales

- Sin listado de expedientes IP en web.
- Sede electrónica no accesible para tablón (HTTP falla / requiere JS).
- Licencias: solo formularios informativos, no concesiones publicadas.

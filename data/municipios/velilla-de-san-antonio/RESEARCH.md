# Velilla de San Antonio — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://ayto-velilla.es |
| Urbanismo (concejalía) | https://ayto-velilla.es/concejalia/urbanismo-obras-y-actividades/ (404 en crawl; contenido vía WP) |
| Categoría WP Urbanismo y Vivienda | REST `wp-json/wp/v2/posts?categories=483` (71 entradas) |
| Trámites municipales (CPT) | REST `wp-json/wp/v2/tramite?per_page=100` (30 trámites) |
| Sede electrónica | https://velilladesanantonio.sedelectronica.es |
| Tablón de anuncios (espublico) | https://velilladesanantonio.sedelectronica.es/board |
| Transparencia | https://ayto-velilla.es/ayuntamiento/transparencia/ |

## Expedientes / proyectos urbanísticos

- **CMS:** WordPress en `ayto-velilla.es` (tema municipal).
- **Listado:** noticias de la categoría «Urbanismo y Vivienda» (id 483) vía REST API JSON.
- **Contenido:** comunicaciones de obras municipales, promociones de vivienda, sector XXIII, remodelaciones, convenios con Catastro, etc. No hay visor de expedientes IP ni tablón urbanístico dedicado en sede.
- **Tablón sede:** 4 anuncios genéricos (convocatorias, IAE, empleo) — sin urbanismo en el momento del scrape.

## Licencias de obra

- **No hay dataset público** de licencias concedidas ni tablón con edictos de licencias.
- **Trámites informativos** en CPT `tramite`: Comunicación Urbanística, Ocupación de Vía Pública, Apertura de Actividad, Apertura Piscinas, Poda y Tala, Licencia Animales Potencialmente Peligrosos.
- Gestión presencial con cita previa (urbanismo@ayto-velilla.es, 91 670 53 00).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SITCM Comunidad de Madrid — `https://idem.comunidad.madrid/geoserver3/ows`, capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='VELILLA DE SAN ANTONIO'` (28 polígonos: UE-1…UE-11, SECTOR-IX VALDEMERA, SECTOR-XXIII, etc.).
- **Estrategia:** tras scrape de título, match por código UE/SECTOR en título o ILIKE sobre `DS_NOMB_AMB`; ejemplo «sector XXIII» → polígono `SECTOR-XXIII`.
- **Limitaciones:** sin visor municipal propio; geometría solo para ámbitos del planeamiento SITCM cuando el título menciona sector/UE. Obras puntuales (parque Sur, plaza Constitución) sin polígono enlazable. No hay licencias georreferenciadas.

## Limitaciones

- Dominio `velilladesanantonio.es` no resuelve DNS; web oficial es `ayto-velilla.es`.
- Sede raíz redirige en bucle; `/board` accesible.
- Sin PDFs de planeamiento en transparencia indexados en el scrape.
- Licencias: solo trámites informativos, no concesiones publicadas.

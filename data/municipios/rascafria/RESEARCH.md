# Rascafría — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `rascafria` |
| Web oficial | https://www.rascafria.org (WordPress 6.6, tema TownPress) |
| Sede electrónica | https://rascafria.sedelectronica.es (espublico gestiona) |
| Dominio `.es` | No responde (500/timeout); usar `.org` |
| Boletín | BOCM (`bocm`), 7 entradas históricas |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Inicio | https://www.rascafria.org/ |
| Urbanismo | https://www.rascafria.org/tu-ayuntamiento/urbanismo/ |
| Ordenación del territorio | https://www.rascafria.org/ordenacion-del-territorio-y-obras-publicas/ |
| Ordenanzas municipales | https://www.rascafria.org/tu-ayuntamiento/ordenanzas-municipales/ |
| Modificación NNSS 1985 | https://www.rascafria.org/aprobacion-inicial-en-los-terminos-que-figuran-en-el-expediente-de-la-modificacion-de-las-normas-subsidiarias-urbanisticas-de-1985/ |
| Anuncios (WP) | https://www.rascafria.org/category/entradas-anuncios/ |
| Sede — dossier trámites | https://rascafria.sedelectronica.es/dossier |
| Sede — tablón | https://rascafria.sedelectronica.es/board/ |
| Sede — transparencia | https://rascafria.sedelectronica.es/transparency |
| WP REST API | https://www.rascafria.org/wp-json/wp/v2/ |

## Proyectos / planeamiento

- **CMS:** WordPress TownPress + WPBakery; sin visor urbanístico propio en la web municipal.
- **Listado:** Páginas estáticas con enlaces a PDFs (formularios licencia en `/tu-ayuntamiento/urbanismo/`), posts WP (modificación NNSS 2023), ordenanzas en `/tu-ayuntamiento/ordenanzas-municipales/`.
- **Búsqueda WP REST:** términos `normas subsidiarias`, `urbanismo`, `planeamiento`, `información pública`, `licencia urban`.
- **SITCM (Comunidad de Madrid):** WFS `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='RASCAFRÍA'` (con tilde). 6 ámbitos:
  - PUERTAS DE LA DEHESA SUR (Estudio Detalle)
  - PUERTAS DE LA DEHESA NORTE (Estudio Detalle)
  - POLÍGONO GANADERO (Plan Parcial)
  - LOS GRIFOS (Plan Parcial)
  - EL MERINEL (Estudio Detalle)
  - AMPLIACIÓN BARRIO DE ARRIBA (Estudio Detalle)
- **Tablón sede:** HTML sin filas (`/board/` vacío al scrapear); anuncios urbanísticos publicados en la web WP.

## Licencias de obra

- **Formularios PDF** en `/tu-ayuntamiento/urbanismo/`:
  - Solicitud licencia obra mayor
  - Solicitud licencia obra menor
  - Solicitud de informes/certificados
- **Ordenanza fiscal** tasa licencias urbanísticas en ordenanzas municipales.
- **Sede espublico:** dossier de trámites accesible; sin listado scrapeable de concesiones.
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDEM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='RASCAFRÍA'`
  - Campo ámbito: `DS_NOMB_AMB`
- **Estrategia:** Descargar polígonos SITCM por municipio; enriquecer proyectos cuyo título coincide con nombre de ámbito (ILIKE / substring). Los 6 ámbitos del planeamiento se insertan como filas `sit_wfs` con `geom_geojson`.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede.
  - Tablón sede vacío; licencias sin polígono.
  - Dominio `rascafria.es` inactivo.
  - CQL requiere municipio con tilde: `RASCAFRÍA` (no `RASCAFRIA`).

## Adapter

- Módulo: `municipio/adapters/rascafria.py`
- Patrón: WordPress TownPress + espublico + SITCM WFS (similar a Aldea del Fresno / Venturada).

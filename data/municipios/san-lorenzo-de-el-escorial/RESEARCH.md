# San Lorenzo de El Escorial — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa (WordPress) | https://www.aytosanlorenzo.es |
| Urbanismo | https://www.aytosanlorenzo.es/servicios/urbanismo/ |
| Modificaciones puntuales | https://www.aytosanlorenzo.es/normativa-municipal/modificaciones-puntuales/ |
| Normas subsidiarias (NNSS) | https://www.aytosanlorenzo.es/normativa-municipal/normas-subsidiarias-san-lorenzo-escorial/ |
| Transparencia — planeamiento | https://transparencia.aytosanlorenzo.es/urbanismo-y-obras-publicas/planeamiento/ |
| Sede electrónica (eAdmin add4u) | https://sede.aytosanlorenzo.es/GDCarpetaCiudadano/ |
| Tablón de anuncios | https://sede.aytosanlorenzo.es/GDCarpetaCiudadano/Tablon.do?action=verAnuncios |
| Trámites urbanismo | https://tramites.aytosanlorenzo.es/urbanismo-obras-y-servicios/ |
| Visor SITCM (CCAA Madrid) | https://idem.madrid.org/cartografia/sitcm/html/visor.htm |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress en dominio principal y subdominio `transparencia.*`; trámites en `tramites.*` (también WP).
- **Planeamiento:** documentación histórica en listas HTML anidadas (`<li>` con PDFs) en transparencia y normativa municipal (acuerdos, memorias, normas, planos, publicaciones BOCM).
- **Tablón sede:** eAdmin `Tablon.do` con filas `verAnuncio&id=…`, documento vía `abrirOriginal(token)` → `ValidarDocumento.do`. Búsqueda POST por `referenciaBusqueda` (el buscador actual devuelve resultados poco filtrados; se parsea igualmente).
- **Licencias:** no hay listado público de concesiones; solo páginas de trámites informativos (obra mayor/menor, apertura, viabilidad, etc.).

## Licencias de obra

- Sin dataset ni tablón de licencias concedidas.
- El adapter recoge **páginas de trámite** del catálogo WP (`tramites.aytosanlorenzo.es/urbanismo-obras-y-servicios/`) como filas informativas (`min_rows: 0` aceptable para concesiones reales).
- Sede `Registrar.do?action=listadoEntradas` incluye trámite 87 «Solicitud de licencia urbanística» pero sin publicaciones de concesión.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro municipio: `DS_MUNICIPIO='SAN LORENZO DE EL ESCORIAL'`
  - Campo ámbito: `DS_NOMB_AMB` (p. ej. `UE-11 CEBADILLAS-POZAS`, `APD-12`)
  - Visor web: SITCM en idem.madrid.org (enlazado desde transparencia)
- **Estrategia:** ingestar los ~29 ámbitos del SITCM como proyectos con `geom_geojson`; enriquecer PDFs/tablón por código UE/APD/SAU en título vía query WFS.
- **Limitaciones:** geometría a nivel de **ámbito de planeamiento**, no de expediente individual ni licencia; tablón y PDFs no enlazan objectId GIS; licencias sin coords.

## Limitaciones generales

- Tablón actual (jul 2026) sin anuncios de urbanismo activos (mayoría fiscal/administrativa).
- Buscador del tablón no filtra bien por término.
- Sin API JSON de expedientes; scrape HTML determinista.
- `www.sanlorenzodelescorial.org` responde 403; dominio operativo es `aytosanlorenzo.es`.

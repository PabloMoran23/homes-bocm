# Colmenarejo — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa (WordPress) | https://www.ayto-colmenarejo.com |
| Oficina Técnica (urbanismo) | https://www.ayto-colmenarejo.com/?page_id=677 |
| Normativa / NNSS | https://www.ayto-colmenarejo.com/?page_id=973 |
| Licencias urbanísticas | https://www.ayto-colmenarejo.com/?page_id=975 |
| Transparencia — planeamiento | https://transparencia.ayto-colmenarejo.org/?page_id=185 |
| Sede electrónica (eAdmin add4u) | https://sede.ayto-colmenarejo.org/eAdmin/ |
| Tablón de anuncios | https://sede.ayto-colmenarejo.org/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo de trámites | https://sede.ayto-colmenarejo.org/eAdmin/Registrar.do?action=inicioPortalTramites |
| Visor SITCM (CCAA Madrid) | https://www.madrid.org/cartografia/sitcm/html/visor.htm |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress 5.0 en `ayto-colmenarejo.com` (tema NewsMagazine); transparencia en subdominio `transparencia.*` (redirige a sede add4u).
- **Planeamiento:** documentación NNSS y modificaciones puntuales en página de normativa (`page_id=973`) con enlaces a PDFs en `wp-content/upLoads/` y legado `fileadmin/SERVICIOS_TECNICOS/NORMATIVA/`.
- **Tablón sede:** eAdmin `Tablon.do` con filas `verAnuncio&id=…`, documento vía `abrirOriginal(token)` → `ValidarDocumento.do`. Búsqueda POST por `referenciaBusqueda`.
- **Licencias:** sin listado público de concesiones; modelos e impresos en página de licencias y normativa; tramitación presencial en Oficina Técnica (miércoles 13:00–14:00).

## Licencias de obra

- No hay dataset ni tablón de licencias concedidas.
- El adapter recoge **modelos PDF** (impresos licencia/declaración responsable, ordenanzas) y **páginas informativas** (Oficina Técnica, sede, tablón).
- Catálogo eAdmin (`Registrar.do?action=listadoEntradas`) incluye trámites urbanísticos pero sin publicaciones de concesión.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro municipio: `DS_MUNICIPIO='COLMENAREJO'`
  - Campo ámbito: `DS_NOMB_AMB` (p. ej. `UE-4 EL POZUELO II`, `S-5.R DEHESA DE LA ESPERNADILLA II`)
  - Visor web: SITCM en madrid.org
- **Estrategia:** ingestar los ~35 ámbitos del SITCM como proyectos con `geom_geojson`; enriquecer PDFs/tablón por código UE/SE/S en título vía query WFS.
- **Limitaciones:** geometría a nivel de **ámbito de planeamiento**, no de expediente individual ni licencia; tablón y PDFs no enlazan objectId GIS; licencias sin coords.

## Limitaciones generales

- Dominios `colmenarejo.es` y `colmenarejo.sedelectronica.es` no operativos; sede real en `sede.ayto-colmenarejo.org`.
- Tablón actual (ago 2026) con pocos anuncios de urbanismo (mayoría fiscal/administrativa; bando limpieza parcelas).
- PDFs legados en `aytocolmenarejo.com/fileadmin/` (dominio antiguo) aún enlazados desde normativa.
- Sin API JSON de expedientes; scrape HTML determinista.

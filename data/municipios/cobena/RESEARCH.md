# Cobeña — investigación portal ayuntamiento

Municipio: **Cobeña** (`cobena`) — Comunidad de Madrid / BOCM

## URLs base

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.ayto-cobena.org |
| Planeamiento | https://www.ayto-cobena.org/tu-ayuntamiento/normativa/planeamiento |
| NNSS y modificaciones | https://www.ayto-cobena.org/tu-ayuntamiento/normativa/planeamiento/nnss-1995 |
| Planes parciales | https://www.ayto-cobena.org/tu-ayuntamiento/normativa/planeamiento/p-parcial |
| Proyectos reparcelación | https://www.ayto-cobena.org/tu-ayuntamiento/normativa/planeamiento/proy-reparcelacion |
| Proyectos urbanización | https://www.ayto-cobena.org/tu-ayuntamiento/normativa/planeamiento/p-urbanizacion |
| Tablón (enlace web) | https://www.ayto-cobena.org/tu-ayuntamiento/tablon-electronico |
| Sede electrónica | https://sede.ayto-cobena.org |
| Tablón sede (ATM) | https://sede.ayto-cobena.org/PortalCiudadano/Tablon/wfrTablon.aspx |
| Transparencia | http://transparencia.ayto-cobena.org/portal |
| Visor planeamiento CM | https://www.comunidad.madrid/servicios/urbanismo-visores |

## CMS y estructura

- **Web:** Fontventa S.L (Bootstrap, acordeones `.acordeonCustomizado`, enlaces PDF en `/media/{hash}/...`).
- **Sede:** ATM eAdministracion (ASP.NET DevExpress, `wfrTablon.aspx`, grid `dxgvDataRow`).
- **Planeamiento:** documentos estáticos en PDF; no hay API JSON ni visor propio del ayuntamiento.

### Listado de expedientes / proyectos

1. **Web planeamiento:** páginas semilla con `list-group-item` y enlaces `/media/*.pdf` (NNSS, planes parciales SAU-3/5A/5B, reparcelación SAU-3, urbanización SAU-3 La Estación).
2. **Tablón sede:** grid DevExpress con anuncios recientes (categoría URBANISMO). Requiere visitar `sede.ayto-cobena.org/` antes para obtener cookie de sesión; sin sesión devuelve «NO DISPONIBLE». Solo primera página (10 filas) en HTML estático; paginación vía callback AJAX.
3. **BOCM:** proyectos ya en `projects.json` (no re-parsear).

### Licencias

- No hay dataset abierto de concesiones con coordenadas.
- El tablón sede puede publicar edictos de licencia (pocas filas visibles en scrape estático).
- Trámites informativos en sede electrónica (catálogo ATM); el adapter incluye páginas informativas de tablón + sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='COBEÑA'` (~38 ámbitos: UE-*, SAU-*, etc.)
  - Visor regional: Visor de Planeamiento Urbanístico de la Comunidad de Madrid (enlace desde web)
- **Estrategia:** tras obtener título del expediente/PDF, buscar código ámbito (`SAU-3`, `UE-7B`, …) o coincidencia textual con `DS_NOMB_AMB` en WFS; rellenar `geom_geojson` en EPSG:4326.
- **Limitaciones:**
  - PDFs del portal sin georreferencia directa.
  - Tablón ATM paginado (no todo el histórico en HTML).
  - Sin visor ArcGIS propio del municipio; dependencia del SIT regional.
  - Nombres en PDF no siempre coinciden exactamente con `DS_NOMB_AMB`.

## Limitaciones generales

- Sede tablón: sesión obligatoria; acceso directo sin cookie falla.
- `planes-parciales` y `proyectos-reparcelacion` son URLs incorrectas (404); slugs correctos: `p-parcial`, `proy-reparcelacion`.
- Página `p-parcial` tiene pocos documentos (3 planes parciales históricos).
- SSL sede: certificado válido; no requiere `insecure_ssl`.

# La Hiniesta — investigación portal ayuntamiento

**Fecha:** 2026-09-20  
**Slug:** `la-hiniesta`  
**BOCYL regional (referencia):** 1 fila

## Resumen

La Hiniesta (Zamora, 304 hab.) publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://ayuntamientolahiniesta.es | WordPress | Turismo, patrimonio, Camino de Santiago; sin sección urbanismo |
| Sede electrónica | https://lahiniesta.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (1 bando servicios), trámites (catálogo inaccesible por redirect) |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | NUM aprobada (c_mun=49095) y 5 sectores WFS |

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumentos y sectores

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_sectores` (5), `plau_cyl_planes_parciales` (0)
- **Filtro:** `n_mun = 'La Hiniesta'`, `c_mun = 49095`
- Sectores: Torre, Travesía Margen Izquierda, Valduercos, Camino Frontón, Iglesia — todos con polígonos WGS84

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://lahiniesta.sedelectronica.es/board
- **Formato:** tabla HTML espublico (enlace `preview-document`)
- Único anuncio visible (jul 2025): bando corte agua potable (no urbanismo)

### 3. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=095`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=095` (vacío)
- Documento NUM: `openDocuIndice.do?cDocId=293548` (aprobación 2016-01-14, BOCyL 2016-12-04)

### 4. BOCyL (referencia externa)

- 1 fila en `ccaa_history_parsed_incremental.csv` (no re-parseada)

## Fuentes de licencias

1. **Tablón sede** — sin licencias publicadas actualmente
2. **Página informativa** — tablón como referencia de trámite (`/board`)
3. **Catálogo trámites** (`/dossier`, `/info`) — bucle de redirección 302; no accesible sin sesión

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono NUM (33 km²)
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 5 polígonos de sector
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='La Hiniesta'`); semillas PlanPublica sin geometría; tablón sin GIS
- **Limitaciones:** sin visor municipal propio; licencias y anuncios del tablón sin georreferencia; sede `/dossier` inaccesible

## Limitaciones

- Web `ayuntamientolahiniesta.es` orientada a turismo, sin documentación urbanística
- Tablón sede: ventana corta, sin API
- Licencias sin geolocalización en fuentes públicas
- Catálogo de trámites de sede con redirect infinito

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (6 filas)
2. Semillas Junta CYL (PLAI/PLAU/NUM) → proyectos de planeamiento
3. Tablón espublico → filtrado por keywords (actualmente sin urbanismo)
4. Página informativa tablón → licencias (trámite, sin concesiones históricas)

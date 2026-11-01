# Santa Cruz de Pinares — investigación portal ayuntamiento

Municipio: **Santa Cruz de Pinares** (`santa-cruz-de-pinares`) — Castilla y León, provincia Ávila. Boletín: `bocyl` (1 aviso). INE: 05222.

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal (Diputación Ávila) | https://www.santacruzdepinares.es/ |
| Normas urbanísticas / enlace PLAU | https://www.santacruzdepinares.es/ayuntamiento/normas-urbanisticas/ |
| Sede electrónica (espublico gestiona) | https://aytosantacruzdepinares.sedelectronica.es/ |
| Tablón de anuncios (sede) | https://aytosantacruzdepinares.sedelectronica.es/board |
| Catálogo trámites (dossier) | https://aytosantacruzdepinares.sedelectronica.es/dossier |
| Transparencia (sede) | https://aytosantacruzdepinares.sedelectronica.es/transparency |
| PlanPublica JCyL (mun. 222) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=222 |
| SIUR visor cartográfico | https://idecyl.jcyl.es/siur/index.html?id=05222 |

**Nota:** `sede.urbanismosantacruz.es` corresponde a otra entidad (Gerencia de Urbanismo de Santa Cruz de Tenerife), no a este municipio abulense.

## Expedientes / planeamiento

- **PlanPublica:** tabla HTML con `doOpen(cDocId, codigo)`; 2 documentos indexados (instrumento sin planeamiento general y anexos).
- **IDECyL WFS:** capa `urbanismo:plau_cyl_instrumentos_ambito` devuelve 1 ámbito «SIN PLANEAMIENTO GENERAL» con geometría `MultiPolygon` del término municipal.
- **Sede tablón:** tabla HTML en `/board` con enlaces `preview-document/{uuid}` (anuncios varios; en oct-2026 sin edictos urbanísticos recientes).
- **Web municipal:** sección normas urbanísticas remite al PLAU; tablón propio en `/ayuntamiento/tablon-de-anuncios/` (noticias administrativas, no expedientes IP).

## Licencias de obra

- No hay listado público de concesiones con coordenadas.
- El **dossier** de la sede incluye trámites de licencias/comunicaciones previas (páginas informativas).
- El adapter registra páginas informativas de trámites + cualquier anuncio del tablón que coincida con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows` — capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun = 'Santa Cruz de Pinares'`.
  - SIUR: visor web por código municipio `05222` (sin API directa por expediente).
- **Estrategia:** ingestar features WFS con `outputFormat=application/json` y `srsName=EPSG:4326`; enriquecer proyectos del tablón/PLAU por coincidencia de título. El único polígono disponible es el ámbito municipal «sin PGOU», no parcelas ni licencias.
- **Limitaciones:** municipio sin sectores ni planes parciales en WFS; tablón sin geometría; licencias sin georreferencia.

## Limitaciones generales

- Certificado SSL de la sede espublico a veces problemático → `insecure_ssl: true` en manifest.
- Tablón sede mezcla empleo público y bandos no urbanísticos (filtros por regex en adapter).

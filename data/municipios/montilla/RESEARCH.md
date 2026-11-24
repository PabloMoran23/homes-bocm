# Montilla (Córdoba) — portal urbanismo

## Fuentes base y semillas

- Sitio principal: `https://montilla.es`
- **Urbanismo (WordPress, multisitio):** `https://urbanismo.montilla.es`
  - Noticias / RSS: `https://urbanismo.montilla.es/feed/`
  - Planeamiento PGOU, documentos, actuaciones en suelo rústico: menú *Planeamiento*
  - Trámites (licencias, declaraciones, comunicación previa): páginas informativas + modelos PDF en `montilla.es/wp-content/uploads/...`
- **Visor UrbanCity:** `https://visorurbanistico.montilla.es/visor`
- **Catálogo / metadatos:** `https://visorurbanistico.montilla.es/geonetwork/srv/spa`
- **Sede electrónica (tablón):** `https://montilla.es/tablon-de-edictos` — aplicación EPRINSA/SPA (Diputación Córdoba); no scrapeado en este adapter (requeriría API o reproducción de flujo específico).

## Listados de expedientes / planeamiento

- No hay listado HTML de expedientes con código tipo “EXP/2025” en la raíz pública revisada.
- **Instrumentos de planeamiento** con geometría descargables vía **WFS GeoServer** embebido en el visor.
- **Noticias de urbanismo** en RSS (títulos, enlaces, fechas) como proxy de proyectos / actuaciones recientes.

## Licencias de obra

- El ayuntamiento publica **información de trámites** (licencia de edificación, DR, comunicación previa) y **modelos/formularios PDF**; no se encontró un tablón municipal con concesiones fechadas por expediente en HTML estático accesible sin la SPA de sede.
- El adapter ingiere las **páginas de trámites** como filas informativas (`fecha_concesion: null`), análogo a otros municipios sin tablón estructurado.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** GeoServer WFS en el host del visor:
  - `GET https://visorurbanistico.montilla.es/geoserver/wfs` con `service=wfs`, `version=2.0.0`, `request=GetFeature`, `typeNames=urbancity_montilla_instrumentos:instrumentos`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Capa de interés: `urbancity_montilla_instrumentos:instrumentos` — propiedades incluyen `name`, `instrument_type_group_name`, `instrument_type_name`, fechas de aprobación/publicación; geometría en polígonos (instrumentos de planeamiento).
  - Otras capas (`urbancity_montilla:gestion`, clasificación, usos, etc.) existen para simbología del visor; para el MVP se usa la capa de **instrumentos** que lleva metadato legible por expediente/instrumento.
- **Estrategia:** descarga paginada `GetFeature` (GeoJSON) y, por fila, `geom_geojson` + URL de la petición acotada por `CQL_FILTER=id=<id>` como trazabilidad.
- **Limitaciones:** geometría corresponde a **ámbitos de planeamiento**, no a licencias de obra puntuales; licencias siguen sin polígono. Sede/tablon en SPA no integrada.
- **Normalización:** algunas geometrías WFS llegan con auto-intersecciones o como `GeometryCollection`; el adapter usa `shapely.make_valid` + unión de polígonos antes de publicar `geom_geojson`.
- **Límite municipal en validación:** el PGOU puede extenderse más allá del polígono administrativo OSM; el `manifest` usa un **bbox holgado** en `geometry.validation.municipal_boundary` para la comprobación `covers`, no el bbox mínimo de Nominatim.

## SSL

- `urbanismo.montilla.es` y `visorurbanistico.montilla.es` usan certificados válidos; no se requiere `insecure_ssl`.

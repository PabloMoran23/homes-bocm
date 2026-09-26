# Puebla de la Sierra — investigación portal ayuntamiento

**Municipio:** Puebla de la Sierra (Comunidad de Madrid, Sierra del Rincón)  
**Fecha:** 2026-08-31  
**BOCM regional (referencia):** 2 avisos

## Resumen

Puebla de la Sierra publica información municipal en su **web WordPress Astra**
(`puebladelasierra.es`) y dispone de **sede electrónica espublico gestiona**
(`puebladelasierra.sedelectronica.es`). Los ámbitos de planeamiento municipal
están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

El municipio es pequeño (~150 hab.) y la publicación de urbanismo es limitada:
no hay visor propio, el tablón de la sede no lista documentos y la sección de
ordenanzas solo contiene el calendario fiscal.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://puebladelasierra.es/` | WordPress Astra | Portal general, ayuntamiento, turismo |
| Ordenanzas | `https://puebladelasierra.es/ayuntamiento/ordenanzas/` | WP HTML + PDF | Solo calendario fiscal 2025 |
| Descarga documentos | `https://puebladelasierra.es/ayuntamiento/descarga-de-documentos/` | WP HTML + PDFs | Solicitudes (licencia obra menor, empadronamiento, etc.) |
| Sede electrónica | `https://puebladelasierra.sedelectronica.es/` | espublico gestiona | Trámites, validación documentos |
| Tablón sede | `https://puebladelasierra.sedelectronica.es/board` | HTML | Sin filas publicadas (redirige a validar documento) |
| Transparencia sede | `https://puebladelasierra.sedelectronica.es/transparency` | HTML Wicket | Sin documentos urbanísticos indexados |
| Visor SITCM | `http://idem.madrid.org/cartografia/sitcm/html/visor.htm` | Visor web | Planteamiento urbanístico CM |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 3 ámbitos `UE-1`, `UE-2`, `UE-3` para `DS_MUNICIPIO='PUEBLA DE LA SIERRA'` |

## Cómo se listan expedientes

- **Planeamiento:** Ámbitos UE en WFS regional SITCM (3 unidades de ejecución, suelo urbano).
- **Web municipal:** Página de descarga de documentos con formularios PDF; sin listado de expedientes activos.
- **Tablón sede:** No operativo (0 documentos en tabla HTML).
- **No hay** visor urbanístico propio del ayuntamiento ni API JSON de expedientes.

## Licencias

- Formulario PDF «Solicitud para licencia de obra menor» en `/ayuntamiento/descarga-de-documentos/`.
- No hay dataset histórico de concesiones con coordenadas.
- La sede no publica licencias concedidas en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='PUEBLA DE LA SIERRA'` (`srsName=EPSG:4326`)
  - Visor SITCM regional (`idem.madrid.org/cartografia/sitcm/html/visor.htm`)
  - 3 ámbitos: UE-1, UE-2, UE-3 (suelo urbano, polígonos Polygon)
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos cuando el título contiene código UE.
- **Limitaciones:** PDFs sin georreferenciación; tablón sede vacío; licencias sin polígono individual; sin PGOU publicado en web.

## Limitaciones

- Municipio muy pequeño con escasa publicación de urbanismo en portal propio.
- Tablón de anuncios de la sede sin documentos publicados.
- Ordenanzas urbanísticas no disponibles en web (solo calendario fiscal).
- Licencias solo como formulario informativo PDF, sin concesiones publicadas.

## Estrategia adapter

1. Semillas de 3 ámbitos SIT WFS (UE-1..UE-3) con `geom_geojson`.
2. PDFs de descarga-de-documentos y ordenanzas filtrados por urbanismo/licencias.
3. Intento de tablón sede (puede devolver 0 filas).
4. Páginas informativas de licencias (formulario obra menor).
5. IDs: `puebla-de-la-sierra-{lic|proy}-{sha256[:14]}`.

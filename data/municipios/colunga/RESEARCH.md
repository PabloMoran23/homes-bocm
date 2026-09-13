# Colunga — investigación portal ayuntamiento

Municipio: **Colunga** (`colunga`) — Asturias / provincia Colunga  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.colunga.es | Liferay DXP — urbanismo, transparencia |
| Urbanismo | https://www.colunga.es/urbanismo | Sección principal urbanismo |
| Instrumentos urbanísticos | https://www.colunga.es/instrumentos-urban%C3%ADsticos | Enlaces RPGUR, PDF planeamiento, BOPA |
| Tramitación de solicitudes | https://www.colunga.es/tramitaci%C3%B3n-de-solicitudes | Formularios licencia obra/actividades |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Colunga | `busquedaConsulta?method=listPublico&idConcejo=19&estado=V` | 70 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://colunga.sede.e-ayuntamiento.es | **404** — no hay sede propia accesible |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=19` (COLUNGA). Tabla HTML paginada (15/página, 70 vigentes en 5 páginas). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/212079/...` (planeamiento, formularios). Enlace directo a RPGUR desde instrumentos urbanísticos. Sin listado estructurado de expedientes en la web — solo documentos estáticos y enlace al registro regional.

3. **Sede / tablón:** No hay sede electrónica municipal accesible (`colunga.sede.e-ayuntamiento.es` devuelve 404).

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal.
- La página de tramitación ofrece formularios PDF (licencia de obra, actividades) pero no concesiones publicadas.
- El adapter devuelve páginas informativas de trámites urbanísticos y formularios descargables.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%COLUNGA%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 3 polígonos municipales en WFS (NSPM id=1132, PGO id=1792, CAU id=2930).
  - Planes especiales, parciales y convenios (67 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sin tablón de licencias — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- Formularios de licencia son trámites informativos, no concesiones publicadas.

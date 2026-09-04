# Villaviciosa — investigación portal ayuntamiento

Municipio: **Villaviciosa** (`villaviciosa`) — Asturias / provincia Villaviciosa  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.villaviciosa.es | Liferay DXP — urbanismo, transparencia |
| Urbanismo | https://www.villaviciosa.es/es/urbanismo | Trámites licencias, oficina técnica |
| PGOU (en trámite) | https://www.villaviciosa.es/pgou | Documentación PGO aprobación inicial, PDFs Liferay |
| Normativa urbanística | https://www.villaviciosa.es/normativa-urbanistica1 | Enlaces instrumentos vigentes |
| Instrumentos vigentes | https://www.villaviciosa.es/instrumentos-de-planeamiento-vigentes | Listado planeamiento |
| Gestión urbanística | https://www.villaviciosa.es/instrumentos-de-gestion-urbanistica | Instrumentos gestión |
| Convenios urbanísticos | https://www.villaviciosa.es/convenios-urbanisticos | Convenios |
| Sede electrónica | https://villaviciosa.sedelectronica.e-ayuntamiento.es | Tablón anuncios, trámites |
| Tablón anuncios | https://villaviciosa.sedelectronica.e-ayuntamiento.es/tablondeanuncios/default.aspx | Anuncios públicos (ASP.NET, paginado) |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento regional |
| Consulta RPGUR Villaviciosa | `busquedaConsulta?method=listPublico&idConcejo=76&estado=V` | ~78 instrumentos vigentes (6 páginas HTML) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=76` (VILLAVICIOSA, INE 33076). Tabla HTML paginada (15/página, ~78 vigentes en 6 páginas). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/262722/...` (PGOU, anuncios BOPA, documentos prioridades, planos). Página PGOU con documentación aprobación inicial marzo 2026. Sin listado estructurado de expedientes individuales — documentos estáticos.

3. **Tablón sede:** Filas `<tr class="clickable">` con enlace `anuncio.aspx?id=N`, fecha y título. Incluye anuncios de información pública urbanística (p. ej. bar-restaurante Plaza Ecce Homo).

## Cómo se publican licencias

- No hay dataset ni listado estructurado de licencias concedidas con coordenadas.
- El tablón de anuncios publica avisos puntuales (información pública, expedientes administrativos).
- La página de urbanismo describe trámites (licencias mayores, obras menores, retejos, etc.) sin registro de concesiones.
- El adapter devuelve páginas informativas de trámites + anuncios del tablón que coinciden con patrón licencia/urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%VILLAVICIOSA%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Instrumentos con polígono WFS (3):**
  - id 442 — NSPM Villaviciosa (normas subsidiarias)
  - id 3091 — PGO Villaviciosa
  - id 3097 — Catálogo urbanístico Villaviciosa
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 3 polígonos municipales en WFS; modificaciones puntuales NSPM, PEPU y planes parciales (~75 instrumentos) sin geometría enlazable.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sin coords; licencias sin georreferencia.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación hasta 6 páginas.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Tablón ASP.NET con paginación postback; adapter scrapea página actual.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR + WFS.

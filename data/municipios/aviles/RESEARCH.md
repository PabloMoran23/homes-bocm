# Avilés — investigación portal ayuntamiento

Municipio: **Avilés** (`aviles`) — Asturias / provincia Avilés  
Boletín: BOPA (`boletin_source_id: bopa`, 6 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://aviles.es | Liferay DXP — urbanismo, licencias, transparencia |
| Urbanismo / licencias | https://aviles.es/urbanismo-licencias-normativa | Índice planeamiento y trámites |
| Planes municipales | https://aviles.es/planes-municipales1 | Enlaces a instrumentos |
| Legado planeamiento | http://www.aviles.es/html_IIS/planes_urban/index.html | PGOU, gestión, información pública (HTML estático) |
| Instrumentos vigentes | http://www.aviles.es/html_IIS/planes_urban/I/I-GEN-PLAN.html | PGOTM, revisiones, planes parciales/especiales |
| Información pública | http://www.aviles.es/html_IIS/planes_urban/I/I-INF_PUB.html | Anuncios IP urbanísticos |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Avilés | `busquedaConsulta?method=listPublico&idConcejo=4&estado=V` | 158 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://sedeelectronica.aviles.es | Tablón de anuncios (`Tablon.aspx`), trámites |
| Licencias particulares | https://aviles.es/licencias-para-particulares | Trámites informativos |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=4` (AVILÉS). Tabla HTML paginada (15/página, 158 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web legado html_IIS:** Índice estático con enlaces a PGOTM, planes parciales/especiales, estudios de detalle, información pública y gestión urbanística. Sin API — scrape de enlaces HTML.

3. **Liferay aviles.es:** Páginas informativas de urbanismo y planes municipales; enlazan al legado html_IIS. Sin listado estructurado de expedientes en curso.

## Cómo se publican licencias

- No hay dataset ni listado público de licencias de obra concedidas en la web municipal.
- La sede electrónica (`sedeelectronica.aviles.es/Tablon.aspx`) publica tablón de anuncios generales; pocas entradas urbanísticas (subvenciones edificación, documentación PGOU).
- El adapter devuelve páginas informativas de trámites de licencias y anuncios del tablón que coinciden con patrones urbanísticos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%AVILES%'`
  - Instrumentos con polígono: PGO AVILES (`Id._Inventario_Registro_Urbanístico=1898`), CAU AVILES (`2209`)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con inventario WFS, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGOU + catálogo ámbitos urbanísticos).
  - Planes especiales, parciales y convenios (156 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sede sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación hasta 11 páginas para Avilés.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Portal aviles.es bloquea User-Agent genérico `curl` (403) — requiere UA identificable.
- Legado html_IIS en `www.aviles.es` (HTTP) coexistiendo con Liferay HTTPS.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

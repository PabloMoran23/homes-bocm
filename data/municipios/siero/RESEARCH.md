# Siero — investigación portal ayuntamiento

Municipio: **Siero** (`siero`) — concejo de Asturias (INE 33066)  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayto-siero.es | WordPress — portal urbanismo, planes, descargas |
| Portal urbanismo | https://www.ayto-siero.es/portal-de-urbanismo/ | Índice urbanismo, enlaces sede y visor |
| Plan general / catálogo | https://www.ayto-siero.es/plan-general-vigente-catalogo-urbanistico-vigente/ | PGOU vigente, catálogo |
| Planes parciales | https://www.ayto-siero.es/desarrollos-de-planeamiento-planes-parciales/ | Listado PP |
| Planes especiales | https://www.ayto-siero.es/desarrollos-de-planeamiento-planes-especiales/ | Listado PE |
| Estudios de detalle | https://www.ayto-siero.es/desarrollos-de-planeamiento-estudios-de-detalle/ | ED en desarrollo |
| Agenda urbana | https://www.ayto-siero.es/agenda-urbana-de-siero/ | Documentación AU |
| Sede SIAC | https://sedeelectronica.ayto-siero.es/siac/ | Trámites, tablón, info pública |
| Info pública urbanística | `Publicaciones.aspx?t=ET&viewall=Y` | Expedientes en trámite |
| Tablón anuncios | `Tablon.aspx` | Anuncios sede |
| Trámites licencias | `Procedimiento_ver_doc.aspx?sol=43,161,179…` | Páginas informativas |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Siero | `busquedaConsulta?method=listPublico&idConcejo=66&estado=V` | Instrumentos vigentes del concejo |
| Visor numeración | https://geonalon.com/NalonMaps/visor_numeracion.php?ayto=siero | Numeración catastral (no urbanismo) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=66` (SIERO). Tabla HTML paginada (~15/página). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación, denominación, expediente, estado.

2. **Web ayto-siero.es:** WordPress con secciones de planeamiento y descargas en `/descarga/{id}/{slug}/{file_id}/{nombre}.pdf`. Sin API JSON pública; crawl HTML de páginas semilla (~80 documentos/páginas urbanísticas).

3. **Sede SIAC — información pública:** `Publicaciones.aspx?t=ET` — listado de expedientes en trámite (puede estar vacío).

4. **Sede SIAC — tablón:** `Tablon.aspx` — anuncios sin licencias estructuradas con coordenadas.

## Cómo se publican licencias

- No hay listado público de licencias concedidas con coordenadas o expediente.
- La sede publica **procedimientos informativos** (licencia obra, comunicación previa, etc.) vía `Procedimiento_ver_doc.aspx?sol=N`.
- El adapter devuelve páginas informativas de trámites y tablón (patrón Pozuelo / otros Asturias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33066` (polígonos del concejo Siero)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por municipio; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo una fracción de los instrumentos RPGUR tienen polígono en el WFS público.
  - Visor numeración GeoNalón es catastral, no enlaza expedientes urbanísticos.
  - Visor SIG (`sigvisor.asturias.es`) requiere JS; sin API REST por expediente.
  - Licencias sin georreferencia pública.
  - Desde algunos entornos cloud `www54.asturias.es` (RPGUR) y el WFS pueden no responder (timeout); el crawl del portal municipal sigue siendo accesible.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación multi-página.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Scrape RPGUR completo implica muchas peticiones (detalle por instrumento).
- Sede info pública y tablón pueden estar vacíos en momentos concretos.

# Gijón y Lugones (Siero) — investigación portal ayuntamiento

Municipio/entidad: **Gijón y Lugones (Siero)** (`gijon-y-lugones-siero`) — parroquia del concejo de **Siero**, Asturias  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)  
Ayuntamiento competente: **Ayuntamiento de Siero** (INE 33066)

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
| Info pública urbanística | `Publicaciones.aspx?t=ET&viewall=Y` | Expedientes en trámite (vacío) |
| Tablón anuncios | `Tablon.aspx` | Anuncios sede (sin licencias estructuradas) |
| Trámites licencias | `Procedimiento_ver_doc.aspx?sol=43,161,179…` | Páginas informativas |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Siero | `busquedaConsulta?method=listPublico&idConcejo=66&estado=V` | ~300 instrumentos vigentes |
| Visor numeración | https://geonalon.com/NalonMaps/visor_numeracion.php?ayto=siero | Numeración catastral (no urbanismo) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=66` (SIERO). Tabla HTML paginada (15/página, ~300 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación, denominación, expediente, estado.

2. **Web ayto-siero.es:** WordPress con secciones de planeamiento y descargas en `/descarga/{id}/{slug}/{file_id}/{nombre}.pdf`. Sin API JSON; crawl HTML de páginas semilla.

3. **Sede SIAC — información pública:** `Publicaciones.aspx?t=ET` devuelve «No existen publicaciones para este grupo» (sin expedientes activos en trámite).

4. **Sede SIAC — tablón:** `Tablon.aspx` accesible pero sin filas GridView de licencias/urbanismo estructuradas.

## Cómo se publican licencias

- No hay listado público de licencias concedidas con coordenadas o expediente.
- La sede publica **procedimientos informativos** (licencia obra, comunicación previa, etc.) vía `Procedimiento_ver_doc.aspx?sol=N`.
- El adapter devuelve páginas informativas de trámites y tablón (como Pozuelo/Gijón).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33066` (48 features para todo el concejo Siero)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por municipio; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo ~48 de ~300 instrumentos tienen polígono en WFS público (cobertura concejo Siero completo, no filtrable por parroquia).
  - Visor numeración GeoNalón es catastral, no enlaza expedientes urbanísticos.
  - Visor SIG (`sigvisor.asturias.es`) requiere JS; sin API REST por expediente.
  - Licencias sin georreferencia pública.

## Limitaciones generales

- Entidad BOCM «Gijón y Lugones (Siero)» es parroquia; datos urbanísticos del ayuntamiento de Siero (concejo completo).
- RPGUR codificación ISO-8859-1; paginación hasta 25 páginas (~300 registros).
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- ~300 instrumentos RPGUR implican ~2 min de scrape con delay 0.35s por detalle.
- Sede info pública y tablón vacíos en el momento de la investigación.

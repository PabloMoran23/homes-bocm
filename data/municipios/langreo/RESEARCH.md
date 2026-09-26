# Langreo — investigación portal ayuntamiento

Municipio: **Langreo** (`langreo`) — Asturias / provincia Langreo, Asturias  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.ayto-langreo.es | Portal municipal (HTTPS con problemas TLS en CI; HTTP redirige a HTTPS) |
| Sede electrónica | https://tramites.ayto-langreo.es | Catálogo trámites, fichas informativas (accesible) |
| Catálogo trámites | https://tramites.ayto-langreo.es/sede/catalogoTramites.do?ent_id=2&idioma=1 | Trámites urbanismo y licencias (carga parcial vía JS) |
| Ficha licencia obra menor | https://tramites.ayto-langreo.es/sede/fichaInformativa.do?asu_cod=287&asu_mod_cod=52 | Cierre de fincas / licencia obra menor |
| Sede alternativa | https://sede.langreo.as/tramites/catalogo-general-de-tramites/tramite-urbanismo | Liferay sede (inaccesible desde CI) |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Langreo | `busquedaConsulta?method=listPublico&idConcejo=31&estado=V` | 45 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=31` (LANGREO). Tabla HTML paginada (15/página, 45 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado. Incluye PGOU vigente, revisiones parciales, planes especiales, catálogo urbanístico, etc.

2. **Sede tramites.ayto-langreo.es:** Catálogo de trámites de urbanismo (licencias, certificaciones). Sin listado estructurado de expedientes en curso ni información pública de planeamiento — solo fichas de trámites.

3. **Web corporativa ayto-langreo.es:** Inaccesible por TLS desde entornos automatizados; no se pudo verificar secciones de urbanismo en portal Liferay/WordPress.

## Cómo se publican licencias

- No hay dataset ni listado público de licencias de obra concedidas.
- La sede electrónica publica fichas informativas de trámites (licencia obra menor, cierre de fincas, certificación urbanística, etc.) sin tablón de anuncios scrapeable.
- El adapter devuelve páginas informativas de trámites de licencias/urbanismo de la sede accesible.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%LANGREO%'`
  - Instrumentos con polígono: PGO LANGREO (`Id._Inventario_Registro_Urbanístico=2867`), CAU LANGREO (`4658`)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con inventario WFS, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGOU + catálogo ámbitos urbanísticos).
  - Planes especiales, parciales y convenios (43 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sede sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación 3 páginas para Langreo.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Portal www.ayto-langreo.es bloqueado por TLS en CI (curl exit 60).
- sede.langreo.as inaccesible desde CI (timeout).
- Sin dataset JSON/API en web municipal; scrape RPGUR + trámites informativos sede.

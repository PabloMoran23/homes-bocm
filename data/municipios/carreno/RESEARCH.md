# Carreño — investigación portal ayuntamiento

Municipio: **Carreño** (`carreno`) — Asturias / provincia Carreño  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayto-carreno.es | Liferay DXP — urbanismo, transparencia |
| Normativa urbanística | https://www.ayto-carreno.es/normativa-urbanistica | Enlaces RPGUR, visor regional, instrucciones planeamiento |
| Estructura PGO | https://www.ayto-carreno.es/estructura-p.g.o. | Memoria, normativa, fichas desarrollo (document_library UUID) |
| Planos de información | https://www.ayto-carreno.es/planos-de-informacion | PDFs clasificación suelo, núcleos rurales |
| Planos ordenación | https://www.ayto-carreno.es/planos-de-ordenacion-suelo-urbano | Planos PGO escala 1/20.000 |
| Documentos info. pública | https://www.ayto-carreno.es/documentos-sometidos-a-informacion-publica | Enlace sede PublicacionTabs |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Carreño | `busquedaConsulta?method=listPublico&idConcejo=14&estado=V` | 43 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php | Mapa interactivo regional (HTML/JS) |
| Sede electrónica | https://sedeelectronica.ayto-carreno.es | Opensiac — trámites, publicación normativa, tablón |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=14` (CARREÑO). Tabla HTML paginada (~15/página, 43 vigentes únicos). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/c/document_library/get_file?uuid=...` y `/documents/...` (memoria PGO, normativa, fichas unidades de actuación, planos). Desde 2023 normativa vigente también en sede electrónica.

3. **Sede / tablón:** `PublicacionTabs.aspx` y `eppublicacion` para expedientes en información pública. **Timeout >45s** en entorno CI — no scrapeable de forma fiable.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- El catálogo de trámites está en sede opensiac (`tramites?method=enter`) pero sin dataset de concesiones.
- El adapter devuelve páginas informativas de trámites urbanísticos y normativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%CARREÑO%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGO id=293, Catálogo urbanístico id=3508).
  - Modificaciones, planes parciales y convenios (41 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sede con tablón con timeout — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con deduplicación por `idInstrumento`.
- Host legacy `rpgur.asturias.es` / `www28.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sede `sedeelectronica.ayto-carreno.es` responde con timeout en CI (>60s).
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

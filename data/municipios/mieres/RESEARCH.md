# Mieres — investigación portal ayuntamiento

Municipio: **Mieres** (`mieres`) — Asturias / provincia Mieres  
Boletín: BOPA (`boletin_source_id: bopa`, 3 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.mieres.es | WordPress TownPress — urbanismo, trámites |
| Urbanismo | https://www.mieres.es/areas-municipales/urbanismo/ | Índice urbanismo, obras y vivienda |
| PGOU | https://www.mieres.es/areas-municipales/urbanismo/plan-general-de-ordenacion-urbana-de-mieres/ | Texto y planos PDF del PGOU |
| Trámites online | https://www.mieres.es/ayuntamiento/instancias-enlaces-a-tramites-online/ | Enlaces sede MI20-* (licencias, DR) |
| Obras y arquitectura | https://www.mieres.es/ayuntamiento/servicios-municipales/obras-urbanismo-y-arquitectura/ | Servicio municipal |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Mieres | `busquedaConsulta?method=listPublico&idConcejo=37&estado=V` | 64 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php?id_instrumento=1487 | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://sedeelectronica.ayto-mieres.es | STA TAO — tablón (`PTS2_TABLON`), trámites |
| Tablón anuncios | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` | `dataset_PTS2_TABLON` embebido (~87 anuncios) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=37` (MIERES). Tabla HTML paginada (15/página, 64 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente (C-XXXX/YY), estado.

2. **Sede STA tablón:** La página `PTS2_TABLON` incluye `var dataset_PTS2_TABLON = [...]` con anuncios (título, fecha, dboid). ~13 entradas urbanísticas (disciplina urbanística, evaluación ambiental de planeamiento).

3. **WordPress mieres.es:** Páginas informativas de urbanismo y PGOU con PDFs en `/wp-content/uploads/`. Sin listado estructurado de expedientes en curso.

## Cómo se publican licencias

- No hay dataset ni listado público de licencias de obra concedidas.
- La sede STA publica tablón de anuncios generales; pocas entradas de disciplina urbanística (no concesiones de licencia).
- Trámites MI20-01 a MI20-13 en web corporativa enlazan a sede electrónica (solicitud licencia, DR, etc.).
- El adapter devuelve anuncios del tablón con patrones urbanísticos + páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33037` (MIERES)
  - Instrumentos con polígono: PGO MIERES (`1888`), PGOU MIERES (`1487`), CAU MIERES (`2931`)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por `id_municipio`; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con inventario WFS, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 3 polígonos municipales en WFS (PGO + PGOU + catálogo ámbitos).
  - Planes parciales, PTE y modificaciones (~61 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sede sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación 5 páginas para Mieres.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Tablón STA tarda ~10s en cargar dataset embebido.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR + tablón embebido.

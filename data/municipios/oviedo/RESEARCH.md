# Oviedo — investigación portal ayuntamiento

Municipio: **Oviedo** (`oviedo`) — Asturias / provincia Oviedo  
Boletín: BOPA (`boletin_source_id: bopa`, 8 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.oviedo.es | Liferay DXP — urbanismo, servicios |
| Urbanismo | https://www.oviedo.es/urbanismo | Concejalía, licencias, planeamiento |
| Transparencia urbanismo | https://transparencia.oviedo.es/urbanismo-y-medio-ambiente | PGO, planes, convenios, licencias |
| PGO | https://transparencia.oviedo.es/urbanismo-y-medio-ambiente/pgo | Fichas ámbitos, catálogo, PDFs suelo |
| Planes parciales | https://transparencia.oviedo.es/urbanismo-y-medio-ambiente/planeamiento-de-desarrollo-planes-parciales-planes-especiales-estudios-de-detalle-y-estudios-de-implantacion/planes-parciales | PDFs AUS con expediente 1191-XXXXXX |
| Actuaciones en tramitación | https://transparencia.oviedo.es/urbanismo-y-medio-ambiente/actuaciones-urbanisticas-en-tramitacion | Proyectos en curso |
| Convenios urbanísticos | https://transparencia.oviedo.es/urbanismo-y-medio-ambiente/convenios-urbanisticos | Convenios publicados |
| Sede electrónica | https://sede.oviedo.es/tramites/licencias | Trámites licencias (sin listado concesiones) |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Oviedo | `busquedaConsulta?method=listPublico&idConcejo=44&estado=V` | 407 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | https://sigvisor.asturias.es/visorurbanismo | Mapa interactivo RPGUR (ArcGIS) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=44` (OVIEDO). Tabla HTML paginada (15/página, 407 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Transparencia Liferay:** PDFs en `/documents/d/participacion-informacion-transparencia/` (planes parciales, estudios de detalle, convenios). Enlaces amigables terminados en `-pdf`. Sin API JSON; scrape HTML de secciones urbanismo.

3. **Web oviedo.es:** PGO con ficheros PDF suelo urbano/no urbanizable. Páginas informativas sin listado estructurado de expedientes.

## Cómo se publican licencias

- No hay listado público de licencias concedidas (tablón de anuncios con concesiones).
- La sede electrónica (`sede.oviedo.es`) publica formularios y trámites (obra mayor/menor, actividades, etc.) pero no un registro de licencias otorgadas.
- Transparencia tiene sección «Licencias urbanísticas» con enlaces a ficheros PDF del PGO (suelo urbano), no concesiones.
- El adapter devuelve páginas informativas de trámites desde sede y transparencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%OVIEDO%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
  - Visor ArcGIS: `https://sigvisor.asturias.es/visorurbanismo`
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 1 polígono municipal en WFS (PGO OVIEDO, id=1797).
  - Planes parciales, especiales y convenios (406 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sin coords de licencias (no hay tablón público).

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- 407 instrumentos vigentes — detalle RPGUR desactivado por defecto (`fetch_rpgur_details: false`) para rendimiento.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

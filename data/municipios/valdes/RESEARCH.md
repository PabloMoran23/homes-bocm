# Valdés — investigación portal ayuntamiento

Municipio: **Valdés** (`valdes`) — Asturias / provincia Luarca/Lluarca, Valdés  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.valdes.es | Liferay DXP — urbanismo, transparencia |
| Urbanismo y vivienda | https://www.valdes.es/urbanismo-y-vivienda | Normativa, PDFs TR distribución, enlaces RPGUR |
| Visor i-cast | http://urbanismo.i-cast.es/Valdes/ | Visor urbanístico municipal (i-cast) — **no responde** |
| Sede electrónica | https://ayuntamientodevaldes.sede.e-ayuntamiento.es | Tablón / trámites — **timeout** |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Valdés | `busquedaConsulta?method=listPublico&idConcejo=34&estado=V` | 31 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | https://sigvisor.asturias.es/visorurbanismo | Visor SIG RPGUR (ArcGIS) |
| Visor legacy | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/ | Mapa interactivo HTML/JS |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=34` (VALDÉS). Tabla HTML paginada (15/página, 31 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado. Ejemplos: PGO Valdés (1869), modificaciones PGO, PE Reforma Interior Cambaral.

2. **Web Liferay:** PDFs en `/documents/51002/...` (tablas de distribución TR, normativa). Sin listado estructurado de expedientes — documentos estáticos en urbanismo-y-vivienda.

3. **Visor i-cast:** Enlazado desde portada pero host `urbanismo.i-cast.es` no responde (HTTP 000).

4. **Sede / tablón:** `ayuntamientodevaldes.sede.e-ayuntamiento.es` timeout — sin scrape de licencias concedidas.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- El tablón de anuncios está en la sede electrónica (inaccesible).
- El adapter devuelve páginas informativas de trámites urbanísticos y enlaces a sede/visor.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%VALD%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 1 polígono municipal en WFS (PGO Valdés id=1869).
  - Planes especiales, parciales y modificaciones (30 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor i-cast y sede inaccesibles — sin coords de licencias.
  - Visor SIG nuevo (`sigvisor.asturias.es`) requiere JS; sin API REST directa por expediente individual.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

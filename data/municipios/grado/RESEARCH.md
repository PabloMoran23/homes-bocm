# Grado — investigación portal ayuntamiento

Municipio: **Grado** (`grado`) — Asturias / provincia Grado  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayto-grado.es | Liferay DXP — urbanismo, revisión PGO |
| Urbanismo | https://www.ayto-grado.es/urbanismo | PGO PDF, catálogo urbanístico, convenios, urbanización Las Dos Vías |
| Revisión PGO | https://www.ayto-grado.es/revision-pgou | Documento prioridades, EAE, participación ciudadana |
| Área rehabilitación | https://www.ayto-grado.es/arearehabilitacion | ARRU |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Grado | `busquedaConsulta?method=listPublico&idConcejo=26&estado=V` | 32 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor Urbanismo en Red | http://urbanismo.i-cast.es/Grado | Visor i-cast (planeamiento municipal) |
| Visor RPGUR | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo regional |
| Sede electrónica | https://sedeelectronica.ayto-grado.es | Tablón de anuncios — **timeout** en CI (~15s+) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=26` (GRADO). Tabla HTML paginada (15/página, 32 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/113029/0/...` (catálogo urbanístico, convenio TSTYC, urbanización Las Dos Vías, revisión PGO). Sin listado estructurado de expedientes — documentos estáticos enlazados desde secciones urbanismo y revisión-pgou.

3. **Sede / tablón:** Tablón de anuncios en sede electrónica; no scrapeable por timeout de red en entorno CI.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- Modelo de declaración responsable de obra menor en PDF en sección urbanismo.
- El tablón de anuncios está en la sede electrónica (inaccesible por timeout).
- El adapter devuelve páginas informativas de trámites urbanísticos y el modelo de obra menor.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%GRADO%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
  - Visor i-cast: `http://urbanismo.i-cast.es/Grado` (sin API REST pública por expediente)
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGO id=1801, Catálogo Urbanístico id=3564).
  - Planes especiales, parciales, modificaciones y convenios (30 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor i-cast y visor RPGUR HTML requieren sesión JS; no API REST directa por expediente individual.
  - Sede con tablón inaccesible — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- Sede electrónica con respuesta lenta o timeout en CI.

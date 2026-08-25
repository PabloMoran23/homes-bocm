# Tapia de Casariego — investigación portal ayuntamiento

Municipio: **Tapia de Casariego** (`tapia-de-casariego`) — Asturias / provincia Tapia de Casariego  
Boletín: BOPA (`boletin_source_id: bopa`, 3 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.tapiadecasariego.es | CMS eDise — urbanismo, documentación PGOU |
| Urbanismo | https://www.tapiadecasariego.es/index.php?M1=2&M2=74 | Enlaces PGOU e Informe Sostenibilidad Ambiental |
| Documentación PGOU | `index.php?M1=1&M2=32&CT=13` (+ subcarpetas SC=17–23) | PDFs en `/images/documentos/documento_*.pdf` |
| Informe Sostenibilidad | `index.php?M1=1&M2=32&CT=14` | Documentación ISA |
| Sede electrónica | https://tapiadecasariego.sedelectronica.es | espublico gestiona — tablón, trámites |
| Tablón de anuncios | https://tapiadecasariego.sedelectronica.es/board | Tabla HTML paginada (Wicket) |
| Catálogo trámites | https://tapiadecasariego.sedelectronica.es/dossier | Trámites urbanismo/licencias |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Tapia | `busquedaConsulta?method=listPublico&idConcejo=70&estado=V` | 37 instrumentos vigentes |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=70` (TAPIA DE CASARIEGO). Tabla HTML paginada (15/página, 37 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo), denominación, expediente, estado.

2. **Web eDise:** Sección Documentación (CT=13) con subcarpetas de normas urbanísticas (suelo urbano, urbanizable, no urbanizable, núcleos rurales). PDFs estáticos en `/images/documentos/`. Sin listado estructurado de expedientes individuales.

3. **Sede espublico tablón:** Tabla HTML con anuncios públicos (EIA, enajenación parcelas, etc.). Enlaces `preview-document/UUID`.

## Cómo se publican licencias

- No hay dataset ni listado histórico de licencias concedidas en la web municipal.
- El tablón de anuncios de la sede publica avisos puntuales (EIA, autorizaciones); no hay filtro dedicado a licencias de obra.
- El catálogo de trámites en `/dossier` incluye procedimientos de licencias urbanísticas.
- El adapter devuelve páginas informativas de trámites + entradas del tablón que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%TAPIA%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGOU id=1814, Catálogo id=2912).
  - Planes especiales, parciales y modificaciones (35 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Licencias del tablón sin coordenadas ni enlace GIS.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Web municipal puede devolver HTTP 429 si se hace crawl agresivo — respetar `request_delay_s`.
- PDFs PGOU en rutas opacas (`documento_NNN.pdf`) sin metadatos estructurados.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR + tablón sede.

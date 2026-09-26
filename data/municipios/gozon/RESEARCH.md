# Gozón — investigación portal ayuntamiento

Municipio: **Gozón** (`gozon`) — Asturias / provincia Gozón  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayto-gozon.org | Liferay DXP — urbanismo, trámites licencias |
| Urbanismo | https://www.ayto-gozon.org/urbanismo | Enlaces a trámites (obra mayor, declaración responsable, etc.) |
| Obra mayor | https://www.ayto-gozon.org/obra-mayor | Formulario licencia obra mayor (PDF) |
| Declaración responsable | https://www.ayto-gozon.org/declaraci%C3%B3n-responsable | Instrucción DR urbanismo + modelos PDF |
| Condiciones de edificación | https://www.ayto-gozon.org/condiciones-de-edificacion | Normativa edificación |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Gozón | `busquedaConsulta?method=listPublico&idConcejo=25&estado=V` | 14 instrumentos vigentes (HTML tabla) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://ayuntamientodegozon.sede.e-ayuntamiento.es | **Inaccesible** — fallo DNS/conexión desde entorno agente |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=25` (GOZÓN). Tabla HTML con 14 instrumentos vigentes: PGOU, catálogo urbanístico, planes especiales (Luanco, Bañugues, Xagó), estudios de detalle, proyectos de actuación y expropiación. Cada fila enlaza a detalle con `idInstrumento`.

2. **Web Liferay:** PDFs en `/documents/201547/...` (instrucción declaración responsable, modelos obra, plano BIC Luanco). Sin listado estructurado de expedientes — solo formularios y documentos estáticos de trámites.

3. **Sede / tablón:** No scrapeable; sede electrónica no resuelve desde el entorno de pruebas.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal.
- Trámites disponibles como formularios PDF: obra mayor, obra menor, declaración responsable, prórroga, primera ocupación, certificado inexistencia infracción.
- Presentación telemática vía sede electrónica (inaccesible en pruebas).
- El adapter devuelve páginas informativas de trámites y documentos normativos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33025` (código RPGUR Gozón, distinto del INE 33031)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por municipio; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - 13 polígonos en WFS vs 14 instrumentos RPGUR (~7 coinciden por id; estudios de detalle y expropiaciones sin geometría enlazable).
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sede con tablón inaccesible — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- Normativa urbanística (`/normativa-urbanistica`) requiere login Liferay.

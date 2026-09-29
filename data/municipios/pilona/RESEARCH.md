# Piloña — investigación portal ayuntamiento

Municipio: **Piloña** (`pilona`) — Asturias / provincia Piloña  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayto-pilona.es | Liferay DXP |
| Urbanismo y vivienda | https://www.ayto-pilona.es/urbanismo-y-vivienda | Formularios licencia obra, enlace RPGUR |
| Normativa urbanística | https://www.ayto-pilona.es/normativa-urbanistica | Enlaces RPGUR y visor mapas urbanísticos |
| Sede electrónica | https://pilona.sedelectronica.e-ayuntamiento.es | e-ayuntamiento (tablón, registro) |
| Tablón anuncios | https://pilona.sedelectronica.e-ayuntamiento.es/tablondeanuncios/default.aspx | HTML tabla (~30 anuncios visibles) |
| Detalle anuncio | `tablondeanuncios/anuncio.aspx?id=N` | Título, fecha, PDF adjuntos |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Piloña | `busquedaConsulta?method=listPublico&idConcejo=48&estado=V` | Instrumentos vigentes (HTML paginado) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA |
| Visor urbanístico | https://sigvisor.asturias.es/visorurbanismo | Visor regional (enlace desde normativa) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET `busquedaConsulta?method=listPublico` con `idConcejo=48` (PILOÑA). Tabla HTML paginada; filas con `idInstrumento`, ámbito, clasificación, denominación, expediente, estado.

2. **Tablón sede:** Listado en `tablondeanuncios/default.aspx` con fecha y título; enlaces `anuncio.aspx?id=`. Incluye avisos urbanísticos puntuales (p. ej. apertura de pista en MUP, normas subsidiarias de concejos vecinos citados en anuncios).

3. **Web Liferay:** PDFs en `/documents/137565/...` (solicitudes de licencia, declaraciones responsables). Sin listado estructurado de expedientes — documentos estáticos y enlaces al RPGUR.

## Cómo se publican licencias

- No hay registro público de licencias concedidas con dirección/coords.
- Formularios descargables en urbanismo-y-vivienda (obra, ocupación vía pública, comunicación previa, etc.).
- Tablón puede publicar anuncios relacionados con obra/actividad; no formato tabular de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%PILO%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Visor HTML: `https://sigvisor.asturias.es/visorurbanismo`
- **Estrategia:** Precargar WFS; al procesar instrumentos RPGUR, adjuntar `geom_geojson` si coincide el id de inventario.
- **Limitaciones:**
  - Solo algunos instrumentos de planeamiento general tienen polígono en WFS público.
  - Planes de desarrollo, licencias y anuncios de tablón sin geometría enlazable.
  - RPGUR puede responder lento o con timeout SSL desde algunos entornos; el adapter tolera fallo y sigue con Liferay/tablón.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; usar host `www54.asturias.es`.
- Tablón mezcla anuncios generales (empleo, animales) con urbanismo — filtro por regex en adapter.
- Formularios de licencia son trámites informativos, no concesiones publicadas.

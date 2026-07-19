# Llanes — investigación portal ayuntamiento

Municipio: **Llanes** (`llanes`) — Asturias / provincia Llanes  
Boletín: BOPA (`boletin_source_id: bopa`, 20 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ayuntamientodellanes.com | Liferay DXP — urbanismo, transparencia |
| Normativa urbanística | https://www.ayuntamientodellanes.com/normativa-urbanistica | Enlaces RPGUR, visor, Dropbox PGOU |
| Documentos en información pública | https://www.ayuntamientodellanes.com/documentos-en-informaci%C3%B3n-p%C3%BAblica1 | Dropbox + PDFs Liferay |
| Documentos sometidos a info. pública | https://www.ayuntamientodellanes.com/documentos-sometidos-a-informacion-publica | Anuncios urbanísticos |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Llanes | `busquedaConsulta?method=listPublico&idConcejo=36&estado=V` | 63 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://llanes.sede.e-ayuntamiento.es | **Inaccesible** — fallo TLS handshake (curl exit 35) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** POST/GET a `busquedaConsulta?method=listPublico` con `idConcejo=36` (LLANES). Tabla HTML paginada (15/página, 63 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/250762/...` (ORDENANZA ORA, reglamentos, instrucciones planeamiento). Carpetas Dropbox para PGOU y documentación en trámite. Sin listado estructurado de expedientes — solo documentos estáticos.

3. **Sede / tablón:** No scrapeable por certificado TLS inválido en `llanes.sede.e-ayuntamiento.es`.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- El tablón de anuncios está en la sede electrónica (inaccesible).
- El adapter devuelve páginas informativas de trámites urbanísticos desde normativa urbanística y enlaces a RPGUR.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%LLANES%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGOU id=6615, Normas provisionales id=7001).
  - Planes especiales, parciales y convenios (61 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sede con tablón inaccesible — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Dropbox links para PGOU no son scrapeables de forma determinista.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

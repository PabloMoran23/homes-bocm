# Cangas de Onís — investigación portal ayuntamiento

Municipio: **Cangas de Onís** (`cangas-de-onis`) — Asturias / provincia Cangas de Onís  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.cangasdeonis.es | Liferay DXP (plataforma i-cast) |
| Normativa urbanística | https://www.cangasdeonis.es/normativa-urbanistica | Enlaces RPGUR, instrucciones planeamiento |
| Documentos sometidos a info. pública | https://www.cangasdeonis.es/documentos-sometidos-a-informacion-publica | Anuncios urbanísticos, estudios, convenios (PDF Liferay) |
| Portal transparencia | https://www.cangasdeonis.es/portal-de-transparencia | Normativa municipal, enlaces transparencia |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Cangas de Onís | `busquedaConsulta?method=listPublico&idConcejo=12&estado=V` | 66 instrumentos vigentes (HTML tabla paginada, 15/página) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://cangasdeonis.sedelectronica.es | **Indeterminada** — página «Sede Electrónica Indeterminada» (sin tablón) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=12` (CANGAS DE ONÍS). Tabla HTML paginada (15/página, 66 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/198558/...` (estudios de detalle SUR3, convenios gestión urbanística, instrucciones planeamiento, BOPA). Sin listado estructurado de expedientes — documentos estáticos en página de información pública.

3. **Sede / tablón:** `cangasdeonis.sedelectronica.es` responde con sede indeterminada; no hay tablón de anuncios scrapeable.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- La sede electrónica no expone tablón de anuncios (instancia indeterminada).
- El adapter devuelve páginas informativas de trámites urbanísticos desde normativa urbanística.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%CANGAS DE ON%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 1 polígono municipal en WFS público (PGOU / instrumento general).
  - Planes especiales, parciales, convenios y estudios (65+ instrumentos) no tienen geometría enlazable en WFS.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sede indeterminada — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- Liferay compartido i-cast (misma plataforma que otros concejos asturianos).

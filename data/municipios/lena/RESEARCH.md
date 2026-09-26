# Lena — investigación portal ayuntamiento

Municipio: **Lena** (`lena`) — Asturias / provincia Lena  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aytolena.es | Liferay DXP — urbanismo, PGOL, transparencia |
| Urbanismo | https://www.aytolena.es/urbanismo | Contacto OTM, enlaces trámites |
| PGOL | https://www.aytolena.es/es/pgol | Plan General de Ordenación de Lena + normas |
| Normativa urbanística | https://www.aytolena.es/es/normativa-urbanistica1 | PDF normas 2006, enlaces PGOL |
| Catálogo | https://www.aytolena.es/es/catalogo | PDF catálogo urbanístico |
| Modificación PP Villayana | https://www.aytolena.es/es/modificado-plan-parcial-villayana | Expediente admin + PDFs |
| Tramitación licencias | https://www.aytolena.es/tramitacion-de-licencias | Trámites informativos |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Lena | `busquedaConsulta?method=listPublico&idConcejo=33&estado=V` | 20 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://lena.sede.e-ayuntamiento.es/action/infopublica?method=enter | Tablón de anuncios — **timeout en CI** (>20s) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=33` (LENA). Tabla HTML paginada (15/página, 20 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/1905982/...` (normas urbanísticas 2006, catálogo, memoria plan parcial Villayana). Páginas temáticas PGOL (suelo urbanizable, núcleos rurales, etc.). Sin listado estructurado de expedientes — documentos estáticos enlazados desde menú urbanismo.

3. **Sede / tablón:** `lena.sede.e-ayuntamiento.es` responde con timeout en el entorno del agente; no scrapeable de forma fiable.

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal accesible.
- La sede electrónica incluye información pública genérica pero no responde en CI.
- El adapter devuelve páginas informativas de trámites (`/tramitacion-de-licencias`) y normativa urbanística.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33033` (13 polígonos municipales)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS por `id_municipio`; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - ~9 de 20 instrumentos RPGUR vigentes tienen polígono en WFS (PGOL, estudios de detalle, plan parcial Sotiello, etc.).
  - Proyectos de expropiación y reparcelación (gestión) no tienen geometría en WFS.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Sede con tablón inaccesible — sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación HTML.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.
- PDFs Liferay con UUID en URL; títulos inferidos del nombre de archivo.

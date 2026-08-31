# Muros de Nalón — investigación portal ayuntamiento

Municipio: **Muros de Nalón** (`muros-de-nalon`) — Asturias / provincia Muros de Nalón  
Boletín: BOPA (`boletin_source_id: bopa`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.murosdenalon.es | Liferay DXP — urbanismo, transparencia |
| Urbanismo y vivienda | https://www.murosdenalon.es/urbanismo-y-vivienda | PGOU, catálogo, revisión parcial, enlaces RPGUR |
| Normativa urbanística | https://www.murosdenalon.es/normativa-urbanistica | RPGUR, visor, documentación PGOU/CAU |
| PGOU | https://www.murosdenalon.es/pgou | Enlaces BOPA aprobación definitiva |
| Catálogo urbanístico | https://www.murosdenalon.es/catalogo-urbanistico | PDFs BOPA + documentación |
| Revisión parcial | https://www.murosdenalon.es/revision-parcial | PDFs Liferay `/documents/` |
| Inventario caminos | https://www.murosdenalon.es/inventario-de-caminos-aprobacion-inicial | Memoria, cartografía, fichas PDF |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Muros | `busquedaConsulta?method=listPublico&idConcejo=39&estado=V` | 42 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php | Mapa interactivo (HTML/JS) |
| Sede electrónica | https://murosdenalon.sedelectronica.e-ayuntamiento.es | Tablón de anuncios accesible |
| Tablón RSS | https://murosdenalon.sedelectronica.e-ayuntamiento.es/tablondeanuncios/tablon_rss.aspx | 20 anuncios recientes (ISO-8859-1) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=39` (MUROS DE NALÓN). Tabla HTML paginada (15/página, 42 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/126814/...` (revisión parcial, inventario caminos, instrucciones planeamiento). Enlaces BOPA externos para PGOU y catálogo. Sin listado estructurado de expedientes en curso — documentos estáticos e info pública.

3. **Sede / tablón:** RSS con títulos y fechas; sin anuncios urbanísticos recientes en el feed (0 de 20 ítems con keywords licencia/obra/planeamiento).

## Cómo se publican licencias

- No hay listado público de licencias concedidas en la web municipal.
- El tablón de anuncios (sede electrónica) es accesible vía RSS pero sin entradas urbanísticas recientes.
- Tasas y normativa de licencias publicadas como PDF en la sección urbanismo (II-1 Tasa por licencias urbanísticas, etc.).
- El adapter devuelve páginas informativas de trámites + normativa PDF.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%MUROS%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Polígonos disponibles: PGO (id=1805), CAU (id=3436)
  - `srsName=EPSG:4326` para GeoJSON WGS84
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 2 polígonos municipales en WFS (PGOU + catálogo).
  - Planes especiales, parciales y modificaciones (40 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sin coords de licencias.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Dominio alternativo `www.murosnalon.es` (sin "de") no resuelve; usar `murosdenalon.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR.

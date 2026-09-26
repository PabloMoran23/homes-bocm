# Noreña — investigación portal ayuntamiento

Municipio: **Noreña** (`norena`) — Principado de Asturias / provincia Noreña  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aytonorena.es | Liferay DXP |
| PGO / Catálogo urbanístico | https://www.aytonorena.es/nore%C3%B1a-pgo | PDFs planos, memoria, normativa, BOPA |
| Proyecto urbanización PL-8 | https://www.aytonorena.es/proyecto-urbanizacion-pl-8 | Actuación urbanística municipal |
| Portal transparencia | https://www.aytonorena.es/portal-de-transparencia | Normativa / contratación |
| Sede electrónica | https://norena.sedelectronica.e-ayuntamiento.es | Trámites y tablón |
| Tablón anuncios | https://norena.sedelectronica.e-ayuntamiento.es/tablondeanuncios/ | Listado HTML + RSS |
| Tablón RSS | `.../tablondeanuncios/tablon_rss.aspx` | ISO-8859-1, items recientes |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento |
| Consulta RPGUR Noreña | `busquedaConsulta?method=listPublico&idConcejo=54&estado=V` | Instrumentos vigentes |
| Visor RPGUR | https://sigvisor.asturias.es/visorurbanismo | Visor regional (mapa urbanístico) |

## Cómo se listan expedientes / proyectos

1. **RPGUR:** Tabla HTML paginada por concejo (`idConcejo=54`, NOREÑA). Detalle en `gestionConsulta?method=retrieve&idInstrumento=N` (p. ej. PGO expediente C-0167/20, id 2959).

2. **Web Liferay:** Página **Noreña PGO** con enlaces `/documents/48435/0/...` (planos escalas 1000–5000, memoria, normativa, catálogo, publicación BOPA 2021).

3. **Tablón sede:** RSS con anuncios generales; pocos avisos de urbanismo explícitos (filtrados por regex en adapter).

## Cómo se publican licencias

- No hay dataset abierto de licencias concedidas en aytonorena.es.
- Trámites y tablón en sede electrónica; el adapter ingiere RSS cuando el título coincide con licencias/obra y páginas informativas del PGO.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro CQL: `Instrumento LIKE '%NORE%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - Visor: https://sigvisor.asturias.es/visorurbanismo
- **Estrategia:** Precargar polígonos WFS; adjuntar `geom_geojson` a filas RPGUR con inventario coincidente.
- **Limitaciones:**
  - WFS puede no responder o ser lento desde algunos entornos; Liferay aporta filas mínimas sin polígono.
  - RPGUR (`www54.asturias.es`) a veces supera timeout de red en CI.
  - Licencias del tablón sin georreferencia.

## Limitaciones generales

- Documentos Liferay sin API JSON; scrape de enlaces PDF.
- Municipio pequeño: pocos instrumentos en RPGUR además del PGO/Catálogo.
- Sin re-parse BOPA; cruce opcional vía `municipio match`.

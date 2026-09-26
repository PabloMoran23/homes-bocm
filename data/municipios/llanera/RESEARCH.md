# Llanera — investigación portal ayuntamiento

Municipio: **Llanera** (`llanera`) — Asturias / provincia Llanera-Asturias  
Boletín: BOPA (`boletin_source_id: bopa`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.llanera.es | Liferay DXP — urbanismo, PGO, normas subsidiarias |
| Urbanismo y vivienda | https://www.llanera.es/urbanismo-y-vivienda | Sección principal urbanismo |
| PGO y catálogo 2023 | https://www.llanera.es/plan-general-ordenación-y-catálogo-urbanístico-2023 | PGO en trámite, PDFs BOPA, estudios ambientales |
| Normas subsidiarias | https://www.llanera.es/normas-subsidiarias | PDFs zonificación por núcleos (Posada, Lugo, Villabona…) |
| Proyectos sectoriales | `/peña-corada`, `/caleras-de-san-cucao`, `/mercasturias`, polígonos Silvota/Asipo | Páginas informativas de actuaciones |
| Sede electrónica | https://sede.llanera.es | Tablón de anuncios accesible |
| Tablón RSS | https://sede.llanera.es/tablondeanuncios/tablon_rss.aspx | Feed XML con anuncios recientes |
| RPGUR (Principado) | https://www54.asturias.es/rpgur/action/publico/welcome | Registro planeamiento — listado por concejo |
| Consulta RPGUR Llanera | `busquedaConsulta?method=listPublico&idConcejo=35&estado=V` | 108 instrumentos vigentes (HTML tabla paginada) |
| Detalle instrumento | `gestionConsulta?method=retrieve&idInstrumento=N` | Metadatos, fechas BOPA, enlace visor |
| Visor urbanístico | http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/html/VisorRPGUR.html | Mapa interactivo (HTML/JS) |

## Cómo se listan expedientes / proyectos

1. **RPGUR (fuente principal):** GET a `busquedaConsulta?method=listPublico` con `idConcejo=35` (LLANERA). Tabla HTML paginada (15/página, 108 vigentes). Cada fila enlaza a detalle con `idInstrumento`. Campos: ámbito, clasificación (General/Desarrollo/Gestión), denominación, expediente, estado.

2. **Web Liferay:** PDFs en `/documents/5416491/...` (PGO, catálogo, normas subsidiarias, acuerdos de pleno). Páginas informativas de proyectos sectoriales (Peña Corada, Mercasturias, polígonos industriales).

3. **Tablón sede:** RSS XML con títulos y fechas. Anuncios de información pública, exposiciones y trámites urbanísticos (solar en mal estado, instalaciones, etc.).

## Cómo se publican licencias

- No hay listado dedicado de licencias concedidas en la web municipal.
- El tablón de anuncios (`sede.llanera.es/tablondeanuncios/`) publica anuncios ocasionales de urbanismo (trámites, exposiciones).
- El adapter incluye páginas informativas de trámites y anuncios del tablón que mencionan licencias/obra.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `Instrumento LIKE '%LLANERA%'`
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` → `idInstrumento` RPGUR
  - `srsName=EPSG:4326` para GeoJSON WGS84
  - Polígonos encontrados: NSPM (id=1794), CAU (id=3919), PGO (id=3093)
- **Estrategia:** Precargar WFS; al procesar cada instrumento RPGUR, si `idInstrumento` coincide con `Id._Inventario_Registro_Urbanístico`, adjuntar `geom_geojson`.
- **Limitaciones:**
  - Solo 3 polígonos municipales en WFS (NSPM, CAU, PGO).
  - Planes parciales, modificaciones y convenios (~105 instrumentos) no tienen geometría enlazable en WFS público.
  - Visor HTML requiere sesión JS; no API REST directa por expediente individual.
  - Tablón sin coords geográficas en anuncios.

## Limitaciones generales

- RPGUR codificación ISO-8859-1; paginación con jsessionid opcional.
- Host legacy `rpgur.asturias.es` no resuelve DNS — usar `www54.asturias.es`.
- Sin dataset JSON/API en web municipal; scrape HTML + RPGUR + RSS tablón.
- `llanera.sedelectronica.es` redirige a sede propia; sede principal operativa en `sede.llanera.es`.

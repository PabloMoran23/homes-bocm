# Santiago de Compostela — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Sede electrónica (STA/TAO) | https://sede.santiagodecompostela.gal/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_HOME&lang=ES | Acceso público |
| Tablón de anuncios | https://sede.santiagodecompostela.gal/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES | `var dataset_PTS2_TABLON = [...]` (~350 edictos) |
| Catálogo de trámites | https://sede.santiagodecompostela.gal/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES | `dataset_CATSERV`; urbanismo filtro keyword `AMB_14` |
| Detalle edicto (ej. PERI-12) | `.../doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES` | PDFs en `/sta/docs/GetDocumentServlet` |
| Web corporativa | https://santiagodecompostela.gal | **Timeout** desde cloud agent (>60s); transparencia/urbanismo no verificable en esta run |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15078&lang=es_ES | Token + cookies; POST `assets/inventario/query_document.php` |
| SIOTUGA tabla PGOM | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | INE 15078, PGOM aprobado 2007-10-03 |
| DOG (IP PERI-12) | https://www.xunta.gal/dog/Publicados/2025/20250421/AnuncioL178-270325-0001_es.html | Exp. 2022/14663C |

## Listado de expedientes / proyectos

1. **Tablón STA**: JSON embebido en HTML (sin API AJAX separada con `KEY=all`). Filtro por remitente `XESTIÓN URBANÍSTICA` y palabras clave (PERI, PXOM, planeamiento). La mayoría de entradas actuales son RRHH.
2. **SIOTUGA**: inventario autonómico con **319** instrumentos de desarrollo (`idclase=13`) y **36** de planeamiento xeral/PXOM (`idclase=14`). Metadatos: `docnome`, `figura`, fechas BOP/DOG.
3. **Catálogo sede**: trámites informativos de urbanismo/licencias (no listado de concesiones).

## Licencias de obra

- No hay dataset público de licencias concedidas en el tablón (unidad gestora «Licenzas de Obra» solo en fichas de trámite).
- El adapter ingiere **páginas de trámite** del catálogo (`Licenza de obra maior`, comunicaciones previas, etc.), al estilo Pozuelo/Medina.
- Archivo municipal: licencias posteriores a 1998 en oficina presencial (documentado en catálogo sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA WMS por concello: `https://siotuga.xunta.gal/siotuga/ws?codine=15078&SERVICE=WMS&REQUEST=GetCapabilities` (capas raster por documento, p. ej. `_15078_MP_*`).
  - Visor SIOTUGA carto: https://siotuga.xunta.gal/siotuga/carto
  - IDEG `POL_AD_PlaneamientoUrbanistico` MapServer (capa SUNc con `CODINE`) — consultas por filtro devolvieron 0 features en pruebas desde cloud.
- **Estrategia:** metadatos de planeamiento vía `query_document.php`; geometría vectorial por expediente no expuesta en API REST simple enlazable al código PERI/SUNP. WMS requiere identificar capa por `iddoc` (getIotpuWMS.php) y es raster.
- **Limitaciones:** sin visor municipal ArcGIS público; web corporativa inaccesible; tablón sin coordenadas; licencias no georreferenciadas. El orquestador aplicará centroide municipal + jitter cuando no hay `geom_geojson`.

## Limitaciones generales

- SSL y rendimiento de la sede: respuestas 30–40s en páginas de detalle.
- `santiagodecompostela.gal` no responde en tiempo útil en el entorno del agente.
- Token SIOTUGA ligado a sesión HTTP (cookie jar obligatorio).

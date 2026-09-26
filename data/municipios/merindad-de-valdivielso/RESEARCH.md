# Merindad de Valdivielso — investigación portal ayuntamiento

Municipio: Merindad de Valdivielso (Burgos, Castilla y León). Código INE municipio PLAI: `09217` (provincia `09`, municipio `217`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.merindaddevaldivielso.es | Drupal 10, tema Toools (Diputación Burgos) |
| Sede electrónica | https://merindaddevaldivielso.sedelectronica.es | espublico gestiona — trámites, tablón, transparencia |
| Tablón de anuncios | https://merindaddevaldivielso.sedelectronica.es/board | Anuncios PDF (Wicket); edictos de dominio/inmatriculación, bandos |
| Catálogo trámites | https://merindaddevaldivielso.sedelectronica.es/dossier/ | 110+ trámites (licencias urbanísticas, planeamiento, ocupación) |
| Transparencia | https://merindaddevaldivielso.sedelectronica.es/transparency | Enlace al tablón; sin sección urbanismo dedicada |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=217 | Sin documentos publicados (tabla vacía) |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=217 | Sin documentos en información pública |
| Archivo histórico JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09217 | Listado legacy planeamiento |

## Expedientes / proyectos

- **Tablón sede:** edictos de expediente de dominio para inmatriculación/reanudación de tracto sucesivo (expediente 173/2026, sept. 2026). Resto de anuncios: presupuesto, bandos, servicios.
- **Catálogo sede:** trámites informativos de planeamiento y actuación urbanística (sin listado de expedientes abiertos).
- **PLAI/PLAU JCyL:** sin filas para este municipio en el archivo consultado.
- **IDECyL WFS:** un instrumento de ámbito municipal (`Sin Planeamiento General`) con polígono MultiPolygon del término municipal.
- **Web Drupal:** sin sección `/urbanismo` ni visor; menú enlaza a sede y tablón.

## Licencias de obra

- No hay concesiones de licencia publicadas en el tablón (solo anuncios administrativos y bandos).
- Trámites disponibles en catálogo sede: declaración responsable/comunicación urbanística, solicitud de licencia o autorización urbanística, modificación/renuncia, ocupación, etc.
- El adapter devuelve páginas informativas de trámite cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capa: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: «Sin Planeamiento General»)
  - Capas vacías: `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Merindad de Valdivielso'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar el polígono municipal del instrumento WFS; enriquecer expedientes del tablón por coincidencia de título con features WFS cuando aplique.
- **Limitaciones:** sin visor municipal ArcGIS; sin sectores/parcelas en WFS; licencias sin georreferencia; expedientes de dominio solo en PDF del tablón.

## Limitaciones

- Municipio sin planeamiento general aprobado registrado en IDECyL (instrumento «Sin Planeamiento General»).
- Tablón sin categoría urbanismo activa con licencias concedidas.
- Drupal corporativo sin descargas PDF urbanísticas en rutas estándar.
- `/dossier` (sin barra final) provoca bucle de redirección; usar `/dossier/`.
- `/info.0` en sede provoca bucle de redirección; el adapter usa solo `/board`.

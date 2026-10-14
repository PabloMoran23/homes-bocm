# Peñaranda de Duero — investigación portal ayuntamiento

Municipio: Peñaranda de Duero (Burgos, Castilla y León). Código INE: `09261` (provincia `09`, municipio `261` en PlanPublica JCyL).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.penarandadeduero.es | Drupal (redirige a `/inicio`) |
| Sede electrónica | https://penarandadeduero.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://penarandadeduero.sedelectronica.es/board | Anuncios Wicket (licencias, plenos, bandos) |
| Catálogo trámites | https://penarandadeduero.sedelectronica.es/dossier.0 | Trámites municipales (licencias urbanísticas, etc.) |
| Transparencia | https://penarandadeduero.sedelectronica.es/transparency | Portal transparencia sede |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=261 | ~30 instrumentos aprobados (NUM/NS, modificaciones puntuales, sector SR-3B, etc.) |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=261 | Sin filas en información pública al investigar |
| Archivo histórico JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09261 | Enlace legacy planeamiento |

## Expedientes / proyectos

- **Principal:** archivo PLAU Junta de Castilla y León — tabla HTML con Libro, Instrumento, fechas y título. Documentos vía `doGoBoletin` / `openDocumento.do?cDocId=`.
- **Geometría:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Peñaranda de Duero'` (9 sectores en capa `plau_cyl_sectores` + instrumentos/parciales).
- **Tablón sede:** anuncios en HTML Wicket (`preview-document/…`); incluye bandos de licencia previa y actas de pleno; parser de tabla + enlaces sueltos.
- **Web Drupal:** menú enlaza sede y tablón; sin visor urbanístico propio en la web corporativa.

Instrumentos PLAU identificados (muestra): NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL, modificaciones puntuales de NS, modificación sector SR-3B (expediente 319/07W), cambios de uso y densidad.

## Licencias de obra

- El tablón publica bandos de **licencia previa** (PDF en `preview-document`).
- No hay listado tabular estructurado de todas las concesiones; predominan anuncios sueltos.
- Trámites informativos en sede (`/dossier.0`): solicitud de licencias y comunicaciones urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Peñaranda de Duero'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PLAU/tablón por códigos de sector (`SR-3B`, etc.) en título.
- **Limitaciones:** sin visor municipal ArcGIS; licencias sin polígono enlazable; geometría WFS a nivel instrumento/sector, no por expediente de licencia; sede usa certificado espublico (adapter con `insecure_ssl`).

## Limitaciones

- Tablón mezcla urbanismo con personal y plenos (filtros por regex).
- PLAU depende de HTML legacy JCyL.
- PLAI vacío en el momento de la investigación.
- Drupal con sitemap mínimo (solo portada indexada).

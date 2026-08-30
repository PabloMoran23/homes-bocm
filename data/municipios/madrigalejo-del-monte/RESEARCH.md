# Madrigalejo del Monte — investigación portal ayuntamiento

Municipio: Madrigalejo del Monte (Burgos, Castilla y León). Código INE: provincia `09`, municipio `197` (`09197`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.madrigalejodelmonte.es | Drupal 10, tema Toools (Diputación Burgos) |
| Ficha municipio | https://www.madrigalejodelmonte.es/pueblos/madrigalejo-del-monte | Datos demográficos + enlace archivo PLAU JCyL |
| Sede electrónica | https://madrigalejodelmonte.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://madrigalejodelmonte.sedelectronica.es/board | Tablón Wicket (vacío en muestra 2026-08) |
| Transparencia | https://madrigalejodelmonte.sedelectronica.es/transparency | Carpeta «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (4 docs) |
| Catálogo trámites | https://madrigalejodelmonte.sedelectronica.es/dossier | Catálogo espublico (lento; timeout >45s en agente) |
| Archivo PLAU JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09197 | Listado histórico planeamiento |
| API PLAU scrape | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=197 | Tabla HTML instrumentos aprobados |
| PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=197 | Sin filas en muestra |

## Expedientes / proyectos

- **Principal:** archivo PLAU Junta de Castilla y León — tabla con Libro, Instrumento, fechas y título. Documentos vía `openDocumento.do?cDocId=` cuando el HTML expone `doOpen`/`doGoBoletin`.
- **Geometría y metadatos:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Madrigalejo del Monte'`.
- **Tablón sede:** vacío (sin filas `preview-document` en `/board` ni `/info`).
- **Transparencia:** 4 documentos en carpeta urbanismo; mayoría administrativa (resolución alcaldía, edictos fiscales).
- **Web Drupal:** sin sección `/urbanismo` dedicada; enlace PLAU en ficha del pueblo.

Instrumentos PLAU identificados (7): NORMAS URBANÍSTICAS MUNICIPALES, modificaciones NUM (SUZ I1/I2/I3, SUZ I2), planes parciales ZDR1/ZDR2/SUZ R2, reclasificación suelo.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón.
- Trámites vía sede (`/dossier`) y páginas informativas enlazadas desde el adapter.
- El adapter devuelve páginas informativas de trámite cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature), `urbanismo:plau_cyl_planes_parciales` (1), `urbanismo:plau_cyl_sectores` (8)
  - Filtro: `CQL_FILTER=n_mun='Madrigalejo del Monte'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PLAU por coincidencia de título o códigos sector (SUZ, ZDR).
- **Limitaciones:** sin visor municipal ArcGIS; licencias sin georreferencia; PLAI vacío; tablón sin anuncios urbanísticos; geometría WFS agregada a nivel instrumento/sector, no expediente individual.

## Limitaciones

- Tablón espublico vacío.
- Catálogo `/dossier` con respuesta lenta (timeout frecuente).
- PLAU: dependencia de HTML legacy JCyL; un documento sin `cDocId` en HTML.
- SSL sede: adapter usa `insecure_ssl` por compatibilidad espublico.

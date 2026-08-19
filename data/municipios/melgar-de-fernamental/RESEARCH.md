# Melgar de Fernamental — investigación portal ayuntamiento

Municipio: Melgar de Fernamental (Burgos, Castilla y León). Código INE municipio PLAI: `09211` (provincia `09`, municipio `211`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://melgardefernamental.es | Drupal 10, tema Toools (Diputación Burgos) |
| Sede electrónica | https://melgardefernamental.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://melgardefernamental.sedelectronica.es/board | Anuncios y actas (Wicket); sin filtro urbanismo dedicado en UI |
| Servicio OBRAS | https://melgardefernamental.sedelectronica.es/citizen-service/c44d8302-4327-4ea9-8679-1810f910fa84 | Trámites/licencias de obras (informativo) |
| Arquitecto municipal | https://melgardefernamental.es/arquitecto-municipal | Enlace a sede, tablón, normativa |
| Normativa | https://melgardefernamental.es/normativa | Impuestos/tributos; sin PDFs urbanísticos embebidos |
| Archivo PLAI JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09211 | Listado histórico planeamiento |
| API PLAI scrape | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=09&municipio=211 | Tabla HTML instrumentos aprobados / en tramitación |
| Diputación Burgos | https://burgos.es/provincia/municipio/melgar-de-fernamental | Metadatos + enlace archivo PLAI |

## Expedientes / proyectos

- **Principal:** archivo PLAI Junta de Castilla y León (`servicios.jcyl.es/PlanPublica`) — tabla con Libro, Instrumento, fechas y título. Documentos descargables vía `openDocumento.do?cDocId=` cuando el HTML expone `doOpen(...)`.
- **Geometría y metadatos:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Melgar de Fernamental'`.
- **Tablón sede:** solo actas de pleno y decretos generales en la muestra actual; anuncios de exposición pública urbanística no aparecen en el tablón reciente.
- **Web Drupal:** sin sección `/urbanismo` ni REST JSON API pública; contenido turístico e corporativo.

Instrumentos PLAI identificados (muestra): NORMAS URBANÍSTICAS MUNICIPALES, modificaciones NUM, plan parcial industrial, estudio de detalle UN-2, PAU polígono El Parralejo, PRAT OTPRAT_24.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón (solo trámites informativos).
- Trámites vía sede (catálogo `/dossier`, servicio OBRAS) y página arquitecto municipal.
- El adapter devuelve páginas informativas de trámite cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Melgar de Fernamental'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PLAI/tablón por coincidencia de título o códigos sector (UN-2, SU-1, PARRALEJO).
- **Limitaciones:** sin visor municipal ArcGIS; licencias sin georreferencia; muchos documentos PLAI sin enlace `doOpen` en HTML (URL genérica del archivo); geometría WFS agregada a nivel instrumento/sector, no expediente individual.

## Limitaciones

- Tablón espublico sin categoría urbanismo activa con expedientes recientes.
- Drupal sin descargas PDF urbanísticas en rutas estándar.
- PLAI: dependencia de HTML legacy JCyL; paginación limitada.
- SSL sede: certificado gestionado por espublico (adapter usa `insecure_ssl` por compatibilidad).

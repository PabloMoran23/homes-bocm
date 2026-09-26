# Merindad de Río Ubierna — investigación portal ayuntamiento

Municipio: Merindad de Río Ubierna (Burgos, Castilla y León). Código INE municipio PLAI: `09229` (provincia `09`, municipio `229`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.merindadderioubierna.es | Drupal 10, tema Toools (Diputación Burgos) |
| Sede electrónica | https://merindadderioubierna.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://merindadderioubierna.sedelectronica.es/board | Licencias urbanísticas y comunicaciones/declaraciones responsables de obra (Wicket, tabla HTML) |
| Normativa | https://www.merindadderioubierna.es/normativa | Ordenanzas fiscales y reglamentos; enlace a revisión NUM |
| Revisión NUM | https://www.merindadderioubierna.es/node/1302 | Anuncio aprobación provisional revisión NORMAS URBANÍSTICAS MUNICIPALES |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=229 | SPG «SIN PLANEAMIENTO GENERAL» |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=229 | Instrumentos en información pública |
| OVC Diputación Burgos | https://ovc.diputaciondeburgos.es/ | Oficina virtual ciudadana (metadatos municipio) |

## Expedientes / proyectos

- **Principal (geometría):** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Merindad de Río Ubierna'` — 85 sectores NUM, 3 planes parciales, 1 instrumento de ámbito (NUM aprobada 2005).
- **Archivo PLAI/PLAU JCyL:** tabla HTML en `servicios.jcyl.es/PlanPublica`; documentos vía `openDocumento.do?cDocId=` / `openDocuIndice.do?cDocId=282892`.
- **Tablón sede:** anuncios de licencias y comunicaciones de obra en localidades del municipio (Quintanilla Sobresierra, Robredo, San Mamés, Villanueva, etc.).
- **Web Drupal:** sin sección `/urbanismo` dedicada; noticias y normativa con enlaces a revisión NUM.

## Licencias de obra

- **Tablón sede** publica licencias urbanísticas y declaraciones responsables/comunicaciones previas con expediente (`404/2026`, `405/2026`, etc.) y PDF en `preview-document/`.
- No hay dataset tabular de concesiones históricas; el adapter ingiere el tablón activo.
- Trámites informativos vía catálogo sede (`/dossier`, timeout frecuente en CI).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Merindad de Río Ubierna'`, `srsName=EPSG:4326`
  - Código municipio WFS: `c_mun=09906`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PLAI/tablón por coincidencia de título o código sector.
- **Limitaciones:** sin visor municipal ArcGIS; licencias del tablón sin georreferencia (solo dirección textual); geometría WFS a nivel sector/instrumento, no expediente individual.

## Limitaciones

- Municipio sin PGOU (SPG «sin planeamiento general»); instrumento vigente es NUM municipal (2005, revisión en trámite).
- Tablón espublico sin filtro urbanismo en UI; hay que parsear categorías «Licencias Urbanísticas» y «Declaraciones Responsables».
- `/dossier` de la sede a veces no responde en entornos CI (timeout).
- SSL sede gestionado por espublico (adapter usa `insecure_ssl` por compatibilidad).

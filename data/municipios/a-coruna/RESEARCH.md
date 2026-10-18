# A Coruña — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.coruna.gal |
| Urbanismo | https://www.coruna.gal/urbanismo/es |
| Exposición pública | https://www.coruna.gal/urbanismo/es/informacion-y-normativa/exposicion-publica?argIdioma=es |
| Planeamiento vigente | https://www.coruna.gal/urbanismo/es/planeamiento/planeamiento-vigente?argIdioma=es |
| Convenios urbanísticos | https://www.coruna.gal/urbanismo/es/informacion-y-normativa/convenios-urbanisticos?argIdioma=es |
| Trámites (licencias) | https://www.coruna.gal/urbanismo/es/informacion-y-normativa/tramites?argIdioma=es |
| Sede electrónica | https://sede.coruna.gal |
| Tablón edictos Concello | https://sede.coruna.gal/opensiac/action/infopublica?method=enter&edictos=true |

## Cómo se listan expedientes / proyectos

- **CMS propio (Urbanismo20)** en `coruna.gal`: listados HTML con `<li class="listadoNormativa">`, enlace `detalle-info-publica/.../contenido/{id}` o `detalle-planteamiento-vigente/.../contenido/{id}`.
- Cada ítem incluye título (`<h1>`) y descripción corta (`property='description'`) con texto del anuncio y código de expediente (`631/…`, `DPE/…`).
- La ficha de detalle añade sección `<section class="fecha">` (fechas en gallego/castellano) y enlace ZIP de documentación vía JavaScript `listaDocumentosMasInfo_*`.
- **Planeamiento vigente** repite el mismo patrón de listado con decenas de instrumentos en tramitación/aprobados.
- **Sede OpenSIAC**: tabla de publicaciones con `method=view&id=…`; el epígrafe «Información urbanística» suele estar vacío en el índice, pero el listado general puede contener anuncios urbanísticos puntuales.

## Licencias de obra

- No hay dataset público de concesiones de licencias con coordenadas (como Madrid).
- **Catálogo de trámites** en urbanismo (p. ej. licencia de demolición, edificación) — páginas informativas, no listado de concesiones.
- **Visor de obras** (infraestructuras): https://ide.coruna.gal/visordeobras/ — estado de obras, no licencias ciudadanas individuales.
- Anuncios de **suspensión cautelar de licencias** aparecen en exposición pública (planeamiento).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS MapServer **planeamiento de desarrollo**: `https://ide.coruna.gal/server/rest/services/Publica/PGM13_WMS_DESARROLLO/MapServer/0` (polígonos, EPSG:25829; query con `outSR=4326`, `f=geojson`).
  - Campos útiles: `DENOMINAC`, `COD_PGOM`, `IDRUD`.
  - Visores web: https://ide.coruna.gal/visorPlaneamiento/ , https://ide.coruna.gal/visores/PGOM13/ (zonificación PGOM, sin enlace directo 1:1 a cada anuncio de exposición).
- **Estrategia:** tras scrape del título/descripción, emparejar tokens (nombre de ámbito, sector S-2, códigos POL/MPP/M22, etc.) contra el índice de polígonos de desarrollo; query puntual por `DENOMINAC` para URL de geometría.
- **Limitaciones:** estudios de detalle en parcela concreta o modificaciones muy localizadas pueden no tener polígono dedicado en la capa de desarrollo; licencias sin GIS; documentación principal en PDF/ZIP sin georreferencia automática.

## Limitaciones generales

- API IGN `nameunit=A Coruña` a veces no devuelve municipio; el manifest incluye `geometry.validation.municipal_boundary` (bbox aproximado) para geocodificación en CI.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Sede: búsqueda POST `method=search` no devolvió resultados fiables sin sesión; se usa listado del tablón + portal urbanismo.
- Paginación: listados actuales caben en una página por sección.
- Rate limiting: `request_delay_s: 0.35`.

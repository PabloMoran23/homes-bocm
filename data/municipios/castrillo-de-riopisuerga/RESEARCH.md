# Castrillo de Riopisuerga — investigación portal ayuntamiento

Municipio: Castrillo de Riopisuerga (Burgos, Castilla y León). Código INE `09088`; PLAU provincia `09`, municipio `088`.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.castrilloderiopisuerga.es | Drupal 9, tema Toools (Diputación Burgos) |
| Sede electrónica | https://castrilloderiopisuerga.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://castrilloderiopisuerga.sedelectronica.es/board | Vacío (sep 2026); sin anuncios urbanísticos publicados |
| Catálogo trámites | https://castrilloderiopisuerga.sedelectronica.es/dossier.0 | 114 trámites; licencias y actuaciones urbanísticas (informativos) |
| Normativa | https://www.castrilloderiopisuerga.es/normativa | Enlace corporativo; sin PDFs urbanísticos embebidos |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=09&municipio=088 | Instrumento «Sin Planeamiento General» (SPG) |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=09&municipio=088 | Sin documentos en información pública (sep 2026) |
| Diputación Burgos | https://ovc.diputaciondeburgos.es/ | Visor cartográfico provincial (no enlazado a expedientes locales) |

## Expedientes / proyectos

- **Principal:** archivo PLAU Junta de Castilla y León — tabla HTML con Libro, Instrumento, fechas y título. Único registro: «SIN PLANEAMIENTO GENERAL» (SPG).
- **Geometría:** IDECyL GeoServer WFS `urbanismo:plau_cyl_instrumentos_ambito` filtrado por `n_mun='Castrillo de Riopisuerga'` (`c_mun=09088`). Devuelve polígono municipal del instrumento SPG.
- **Tablón sede:** vacío; no hay edictos ni exposiciones públicas recientes.
- **Web Drupal:** sin sección `/urbanismo` dedicada; contenido turístico, corporativo y normativa general.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón.
- Trámites informativos vía catálogo sede (`/dossier.0`): licencia urbanística, comunicación previa, licencia de ocupación, certificado urbanístico, etc.
- El adapter devuelve páginas informativas de trámite cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capa: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature con `MultiPolygon` en EPSG:4326)
  - Filtro: `CQL_FILTER=n_mun='Castrillo de Riopisuerga'` o `c_mun='09088'`
- **Estrategia:** ingestar feature WFS del ámbito municipal SPG como proyecto con `geom_geojson`; enriquecer filas PLAI/tablón por coincidencia de título o código sector si aparecen en el futuro.
- **Limitaciones:** sin visor municipal ArcGIS ni planes parciales/sectores; solo polígono de ámbito municipal (SPG); licencias sin georreferencia; tablón vacío.

## Limitaciones

- Municipio sin planeamiento general aprobado (solo declaración SPG en PLAU).
- Tablón espublico sin anuncios activos.
- Drupal sin descargas PDF urbanísticas en rutas estándar.
- Catálogo dossier requiere sesión previa (`/info`) para evitar bucle de redirección.
- SSL sede: adapter usa `insecure_ssl` por compatibilidad con certificados espublico.

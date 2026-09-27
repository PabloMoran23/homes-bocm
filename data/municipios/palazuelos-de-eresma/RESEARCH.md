# Palazuelos de Eresma — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://palazuelosdeeresma.es | WordPress; secciones urbanismo y trámites destacados |
| Urbanismo y obras | https://palazuelosdeeresma.es/urbanismo-y-obras/ | Enlace al archivo PLAU JCyL (provincia 40, municipio 155) |
| Trámites destacados | https://palazuelosdeeresma.es/tramites-destacados/ | Solicitud de licencia urbanística (sede) |
| Sede electrónica | https://palazuelosdeeresma.sedelectronica.es | espublico gestiona (ehome) |
| Tablón de anuncios | https://palazuelosdeeresma.sedelectronica.es/board/ | Tabla HTML con `preview-document` |
| Trámites | https://palazuelosdeeresma.sedelectronica.es/dossier | Catálogo de trámites (respuesta lenta) |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=155 | ~15 documentos de planeamiento |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=155 | Información pública instrumentos |
| SIUR IDECyL | https://idecyl.jcyl.es/siur/index.html?id=40155 | Visor urbanístico regional (referencia) |

## Listado de expedientes / proyectos

- **Principal:** tabla HTML en PlanPublica (`searchVPubDocMuniPlau` / `searchVPubDocMuniPlai`) con filas `<tr>` y enlaces `openDocumento.do?cDocId=…`.
- **Complemento:** tablón espublico (documento, expediente, procedimiento, categoría, descripción, fecha).
- **No hay** visor municipal propio ni API JSON de expedientes en la sede.

## Licencias

- No se publican concesiones de licencia de obra de forma sistemática en el tablón.
- Trámite «Solicitud de Licencia o Autorización Urbanística» accesible desde la web y sede `/dossier`.
- El adapter devuelve trámites del catálogo cuando existen + filas del tablón que coincidan con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Palazuelos de Eresma'` (INE 40155)
  - ~5 sectores con polígono en WFS
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PLAU/tablón con `_attach_geometry` buscando códigos de sector en el texto.
- **Limitaciones:** tablón sin coordenadas; licencias sin GIS; `/dossier` muy lento; no hay visor ArcGIS municipal.

## Limitaciones generales

- Paginación del tablón limitada a la página principal en el scrape actual.
- Boletín regional: BOCYL (`bocyl`), 1 aviso histórico en el dataset del repo.

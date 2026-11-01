# San Miguel del Arroyo — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sanmigueldelarroyo.sedelectronica.es/ | espublico gestiona (Wicket); tablón, trámites, transparencia |
| Tablón de anuncios | https://sanmigueldelarroyo.sedelectronica.es/board/ | Tabla HTML con `preview-document` (PDFs anunciados) |
| Catálogo trámites | https://sanmigueldelarroyo.sedelectronica.es/dossier | Enlaces `/catalog/t/...` |
| Transparencia | https://sanmigueldelarroyo.sedelectronica.es/transparency | Categoría 7 «Urbanismo, Obras Públicas y Medio Ambiente» (10 docs) |
| Web municipal (Dip. Valladolid) | https://sanmigueldelarroyo.ayuntamientosdevalladolid.es/el-municipio/urbanismo | Enlaces IDE Valladolid / observatorio |
| Normativa urbanística | https://sanmigueldelarroyo.ayuntamientosdevalladolid.es/el-ayuntamiento/administracion-municipal/normativa-urbanistica | Modificación Puntual 1/2016 NUM (PDF) |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=47&municipio=145 | Instrumentos aprobados (NUM, modificaciones) |
| PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=47&municipio=145 | Información pública |

Dominio `sanmigueldelarroyo.gob.es` redirige a la sede (`/info.0`).

## Expedientes / planeamiento

- **Tablón sede:** filas con expediente, procedimiento, categoría (incl. Urbanismo), fecha y enlace PDF vía `preview-document`.
- **PLAU:** tablas HTML con `doGoBoletin` / `openDocumento.do?cDocId=…` — principal fuente de instrumentos (NUM vigente, modificaciones puntuales).
- **No hay** consulta pública de expedientes urbanísticos individuales sin autenticación (solo trámites informativos en dossier).

## Licencias de obra

- Publicadas en el **tablón** cuando el ayuntamiento las anuncia (categoría/procedimiento licencias).
- Trámites informativos en `/dossier` (licencia obra mayor/menor, comunicación previa, etc.) sin listado de concesiones históricas.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'San Miguel del Arroyo'` (código `c_prov_mun` = 47145)
  - Campos útiles: `c_id_sect`, `n_num_sect`, `n_sector`, `url_doc_info`, geometría poligonal en GeoJSON (`EPSG:4326`)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer anuncios del tablón/PLAU buscando códigos de sector (`SUDOD 01`, etc.) vía query puntual a `plau_cyl_sectores`; para documentos NUM usar polígono del ámbito municipal en `instrumentos_ambito`.
- **Limitaciones:** La web municipal enlaza a cartografía provincial (IDE Valladolid) sin capa de expediente enlazable; licencias del tablón suelen ser PDF sin georreferencia explícita. El IGN OGC API no devuelve límite municipal por nombre exacto «San Miguel del Arroyo» (H03: `municipal_boundary_unavailable`); el polígono NUM de IDECyL WFS requiere `buffer(0)` por topología inválida en origen.

## Limitaciones generales

- Certificado SSL de la sede: el adapter usa `insecure_ssl` (patrón otros municipios espublico).
- Paginación del tablón no probada con muchos anuncios (actualmente pocas filas).
- Sin API JSON pública en sede; scrape HTML determinista.

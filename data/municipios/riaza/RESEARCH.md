# Riaza — investigación portal ayuntamiento

**Municipio:** Riaza (Castilla y León, Segovia)  
**Slug:** `riaza`  
**BOCyL:** 1 expediente en corpus (`bocyl`)

## Fuentes

| Fuente | URL | Notas |
|--------|-----|-------|
| Web corporativa (Liferay Segovia9) | https://www.riaza.es | Dominio propio; tema Diputación Segovia |
| Actualidad municipal | https://www.riaza.es/actualidad-municipal | Noticias (Asset Publisher `hr5A`); NNSS 2025 publicada en abril 2025 |
| Trámites municipales | https://www.riaza.es/tramites-municipales | Formularios licencia obra menor, autoliquidación tasas urbanísticas |
| Publicaciones oficiales | https://www.riaza.es/publicaciones-oficiales | Bandos y publicaciones |
| Normativa | https://www.riaza.es/normativa | Normativa local |
| Vivienda | https://www.riaza.es/vivienda | Información vivienda |
| Sede electrónica (espublico gestiona) | https://riaza.sedelectronica.es | Tablón `/board`, catálogo `/dossier`, consulta expedientes |
| Archivo PLAI JCYL | https://servicios.jcyl.es/PlanPublica | Provincia 40, municipio **170** (Riaza) |

## Proyectos / planeamiento

- **PLAI JCYL:** documentos aprobados e información pública (p. ej. NNSS núcleos anejos a Riaza).
- **Web:** noticias de información pública (NNSS municipales, BOCyL).
- **Tablón sede:** anuncios con enlace `preview-document` (pocos registros activos).
- No hay visor urbanístico municipal propio ni listado de expedientes IP en la web.

## Licencias

- No hay dataset público de concesiones con coordenadas.
- Formularios y tasas en `/tramites-municipales` y catálogo sede (`/dossier`).
- Tablón sede para edictos de licencias (si se publican).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL GeoServer WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'Riaza'`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas de tablón/PLAI/web por coincidencia de título o código de sector.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin georreferencia; polígonos WFS son ámbitos de planeamiento (sectores), no expedientes individuales del tablón.

## Limitaciones técnicas

- Sede requiere cookies (`JSESSIONID`) para tablón — el adapter usa cookie jar.
- SSL sede: `insecure_ssl: true` en manifest (patrón CYL espublico).
- Paginación PLAI limitada a 4 páginas por modo (aprobado / info pública).

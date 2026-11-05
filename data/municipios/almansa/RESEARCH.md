# Almansa — investigación portal ayuntamiento

Municipio: **Almansa** (`almansa`), provincia Albacete, Castilla-La Mancha. INE **02009**.

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Web oficial | https://almansa.es | WordPress + WooCommerce; REST API pública (`/wp-json/`) |
| Trámites (obra/licencias) | https://almansa.es/tramites/obra-menor , `/obra-mayor` | Páginas informativas «Mis Ayto» |
| Biblioteca documentos | https://almansa.es/documentos | CPT `dlp_document`; API `wp/v2/dlp_document` |
| Sede electrónica | https://almansa.sedipualba.es | ASP.NET Sedipualba (Dip. Albacete) |
| Tablón anuncios | https://almansa.sedipualba.es/tablondeanuncios/default.aspx | HTML paginado |
| Tablón RSS | https://almansa.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1 |
| Catálogo trámites sede | https://almansa.sedipualba.es/catalogoservicios.aspx | Trámites genéricos (registro, reclamaciones); urbanismo vía web WP |
| Área Obras (sede) | https://almansa.sedipualba.es/catalogoservicios.aspx?area=353&ambito=1 | Enlace de área; sin listado urbanístico detallado en scrape |
| Transparencia | https://almansa.es/portal-de-transparencia | Documentos administrativos |

## Cómo se listan expedientes / proyectos

- **Biblioteca WP (`dlp_document`):** PDFs publicados (p. ej. «ESTUDIO DE DETALLE MANZANA E-2 del SUP 3», ordenanzas urbanísticas, plan movilidad). Listado vía REST paginado.
- **Tablón Sedipualba:** RSS + HTML. Edictos de actividad (`CA-xxxx`), publicaciones tablón municipal (`OFxx/yy`), plenos, personal.
- **PGOU regional:** metadatos + polígono municipal en ArcGIS CLM (no expedientes individuales).
- No hay visor urbanístico municipal ni API de expedientes abiertos.

## Licencias de obra

- No hay registro histórico público de licencias concedidas.
- Trámites informativos en `almansa.es/tramites/*` (obra mayor/menor, licencia actividad).
- Tablón publica edictos puntuales (actividad, publicaciones OF) cuando el ayuntamiento los inserta.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM `https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0` — query `COD_INE='02009'` o `MUNICIPIO='Almansa'` → polígono **PGOU** (GeoJSON WGS84, `DESCARGA` ZIP ficheroscomunes.castillalamancha.es).
  - Sin visor municipal ArcGIS/WFS enlazado a expediente.
  - Tablón/PDF sin georreferencia explícita.
- **Estrategia:** fila proyecto PGOU con `geom_geojson` del servicio regional; documentos/tablon sin geometría (centroide municipio + jitter en orquestador).
- **Limitaciones:** CLM no distingue parcelas/expedientes; WP mezcla documentos no urbanísticos (filtrado por regex).

## Limitaciones generales

- Catálogo sede casi solo trámites transversales; planeamiento principalmente en web WP + tablón.
- Tablón mezcla personal/subvenciones; filtrado regex.
- Presentación telemática requiere certificado; sin API pública de expedientes urbanísticos.

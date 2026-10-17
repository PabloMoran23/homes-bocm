# Santervás de la Vega — investigación portal ayuntamiento

**Municipio:** Santervás de la Vega (Castilla y León, Palencia)  
**INE:** 34146  
**Fecha:** 2026-10-17

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial (WP Divi, servicio Dip. Palencia) | https://santervasdelavega.es | Noticias, corporación, urbanismo |
| Urbanismo (galería planeamiento) | https://santervasdelavega.es/ayuntamiento/urbanismo/ | Secciones `?g=10&st=0..2` (documentación, en tramitación, cerrado) y licencias `?g=20` |
| Proyecto delimitación suelo urbano | https://santervasdelavega.es/urbanismo/proyecto-delimitacion-suelo-urbano/ | PDF normativa y planos (`/files/2018/08/`) |
| Sede electrónica (espublico gestiona) | https://santervasdelavega.sedelectronica.es/board | Tablón de anuncios |
| Trámites | https://santervasdelavega.sedelectronica.es/dossier | Catálogo (sin licencias urbanísticas destacadas en scrape) |
| PLAU / PlanPublica JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=146 | NUM 2016, modificación NUM 2020, OTDOAS provincial |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=146 | Sin expedientes en IP al revisar (2026-10) |
| Visor SIUR IDECyL | https://idecyl.jcyl.es/siur/index.html?id=34146 | Visor cartográfico regional |

## Cómo se listan expedientes

- **Web municipal:** plugin Aytos/Diputación de Palencia con galerías por estado (`g=10`, `st=`) y fichas de detalle bajo `/urbanismo/...` con enlaces a PDF estáticos.
- **Tablón sede:** tabla HTML espublico con `preview-document` (documento, expediente, procedimiento, categoría, descripción, fecha). En la revisión predominan avisos tributarios/fiscales.
- **PLAU JCYL:** listado tabular PlanPublica con enlaces `openDocumento.do?cDocId=...` para instrumentos aprobados.
- **REST API WordPress:** deshabilitada (`401 No REST API`) para usuarios anónimos.

## Cómo se publican licencias

- Sección «Licencias y otros actos de intervención en el uso del suelo» (`?g=20`) sin listado histórico de concesiones en la web revisada.
- No hay dataset abierto de licencias concedidas.
- Sede: trámites genéricos; sin filas de licencia de obra en tablón en el momento del scrape.
- Estrategia adapter: páginas informativas de trámites si aparecen en catálogo + tablón si publican licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capa principal: `urbanismo:plau_cyl_instrumentos_ambito` con `n_mun = 'Santervás de la Vega'`
  - 1 polígono MultiPolygon (ámbito NUM) en EPSG:4326
  - Capas `plau_cyl_sectores` / `planes_parciales`: sin features para este municipio en WFS
  - SIUR visor regional (sin API expediente→polígono por licencia)
- **Estrategia:** ingestar el instrumento WFS como proyecto con `geom_geojson`; propagar geometría a documentos PLAU/web relacionados con NUM/planeamiento vía `_attach_geometry`.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS propio.
  - Proyecto delimitación suelo urbano solo en PDF (2018), sin geometría vectorial en portal.
  - Licencias sin georreferencia pública.
  - Municipio pequeño (~1.100 hab.); volumen bajo de publicaciones activas.

## Limitaciones generales

- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
- Web alojada en plataforma Diputación de Palencia (`aytos.dip-palencia.es` cookies/accesibilidad).
- Certificado sede puede requerir `insecure_ssl` en algunos entornos CI.

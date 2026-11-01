# San Juan de la Rambla — investigación portal ayuntamiento

Municipio: **San Juan de la Rambla** (`san-juan-de-la-rambla`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
BOC: `boc_canarias` (1 entrada en `projects.json`)

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://www.sanjuandelarambla.es/ | WordPress (Divi); área Urbanismo |
| Sede electrónica | https://sede.sanjuandelarambla.es/ | Galileo GIYS (`galileoiys.es`) |
| Tablón edictos | https://sede.sanjuandelarambla.es/publico/tablon | ASP.NET + enlaces `/publico/edictos/{id}` |
| RSS edictos | https://sede.sanjuandelarambla.es/publico/sindicacion/edictos/RSS | Sindicación XML |
| Procedimientos | https://sede.sanjuandelarambla.es/publico/procedimientos | Catálogo trámites (URBANISMO) |
| Info territorial | https://sede.sanjuandelarambla.es/publico/territorio/informeurbanistico | Informe urbanístico |
| Localización expedientes | https://sede.sanjuandelarambla.es/publico/territorio/cexp | Visor WMS `38034_CEXP` (capas EXPEAB/EXPECE) |
| Transparencia | https://transparencia.sanjuandelarambla.es/ | Normativa e iniciación normativa |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-san-juan-de-la-rambla | CKAN, 9 recursos / 3 instrumentos |
| GeoBDP municipio | https://geobdp.grafcan.es/core/municipios/38034/ | INE 38034; visor polígonos por documento |

## Expedientes / proyectos

- **SITCAN CKAN:** PGO (adaptación DL 1/2000), normas subsidiarias, plan parcial Los Toscales P.P.13; recursos enlazan IDE Canarias y GeoBDP (`/core/documentos/{id}.html`).
- **Sede:** tablón y RSS de edictos (pocos ítems recientes; filtro urbanístico en adapter).
- **WordPress:** noticias PMUS, participación ciudadana y tablón de edictos; sin sección de expedientes en información pública estructurada.

Formato: CKAN JSON API + HTML tablón/RSS + PDFs en IDE Canarias.

## Licencias de obra

- **No hay listado público de licencias concedidas** con coordenadas.
- Trámites informativos en sede (procedimientos URBANISMO) e informe urbanístico.
- Edictos RSS/tablón pueden publicar licencias puntuales (regex en adapter).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoBDP GRAFCAN: `https://geobdp.grafcan.es/core/documentos/{doc_id}.html` — `App.Map.zoomToExtent({FeatureCollection})` en UTM28N → WGS84 en adapter.
  - Catálogo: `https://geobdp.grafcan.es/core/municipios/38034/`
  - Sede visor expedientes: WMS `http://cit.galileoiys.es/ServicioMapas.aspx?map=38034_CEXP` (capas `EXPEAB38034`, `EXPECE38034`, campo `NUM_EXPE`) — dominio no resuelve desde entornos cloud; sin API GeoJSON pública directa.
- **Estrategia:** emparejar título SITCAN ↔ doc_id GeoBDP; polígonos de planeamiento. Expedientes del visor municipal no integrados por indisponibilidad de `cit.galileoiys.es` en CI.
- **Limitaciones:** geometría solo para ~3 instrumentos de planeamiento en SITCAN/GeoBDP; tablón/edictos sin GIS; visor expedientes sede no automatizable desde este entorno.

## Limitaciones generales

- Sede Galileo sin API JSON para tablón (scrape HTML + RSS).
- WordPress REST requiere login; solo sitemaps y páginas públicas.
- SSL estándar en sede.
- Sin re-parse BOCM.
